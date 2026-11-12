"""Provider for tokens that keep each role in one address variable
(for example `owner`, `minter`). Config section (framework: single_address_roles):

  roles:
    - name: minter
      event: {abi: token, name: NewMinter, arg: newMinter}   # Setter event and the address argument
      read: {abi: token, function: minter}                   # On-chain reader for validation
    - name: proxyAdminOwner
      source: proxyAdmin      # Read events and values at the address of an earlier role. Default: the token.
      start_block: 0          # First block to scan. Default: the token start_block.
      event: {...}
      read: {...}
"""

from dataclasses import dataclass

from rwa_access.core.abi import AbiError, Event
from rwa_access.core.models import RoleHolder, Token
from rwa_access.core.reads import Reader
from rwa_access.core.replay import replay_latest
from rwa_access.evm import is_zero, same_address
from rwa_access.providers.base import ProviderConfig, StockProvider

# Resolved role values of one token so far: {role name: address or None}.
Resolved = dict[str, str | None]


@dataclass(frozen=True)
class RoleSpec:
    name: str
    event: Event
    arg: str  # Event argument that holds the new address
    reader: Reader | None
    source: str | None  # Earlier role whose address emits the event. None: the token.
    start_block: int | None

    @classmethod
    def from_config(cls, raw: dict, abis, earlier: list[str]) -> "RoleSpec":
        event = abis.get(raw["event"]["abi"]).event(raw["event"]["name"])
        arg = raw["event"]["arg"]
        if event.param(arg).type != "address":
            raise AbiError(f"Role '{raw['name']}': argument '{arg}' of {event.signature} is not an address")
        source = raw.get("source")
        if source is not None and source not in earlier:
            raise ValueError(f"Role '{raw['name']}': source '{source}' must be a role defined above it")
        return cls(
            name=raw["name"],
            event=event,
            arg=arg,
            reader=Reader.from_config(raw["read"], abis) if "read" in raw else None,
            source=source,
            start_block=raw.get("start_block"),
        )

    def address(self, token: Token, resolved: Resolved) -> str | None:
        return token.address if self.source is None else resolved.get(self.source)


class StorageRoleProvider(StockProvider):
    def __init__(self, config: ProviderConfig, ctx=None):
        super().__init__(config, ctx)
        self.role_specs: list[RoleSpec] = []
        for raw in config.raw["roles"]:
            spec = RoleSpec.from_config(raw, config.abis, [s.name for s in self.role_specs])
            self.role_specs.append(spec)
        # (token address, role) -> value from logs. None means "no event found".
        self.expected: dict[tuple[str, str], str | None] = {}
        self.resolved: dict[str, Resolved] = {}

    def role_names(self) -> list[str]:
        return [spec.name for spec in self.role_specs]

    def context_value(self, token: Token, name: str) -> str | None:
        return self.resolved.get(token.address, {}).get(name)

    def collect(self, block: int) -> list[RoleHolder]:
        holders: list[RoleHolder] = []
        for token in self.tokens:
            resolved: Resolved = {}
            for spec in self.role_specs:
                source = spec.address(token, resolved)
                change = None
                if source is not None and not is_zero(source):
                    start = token.start_block if spec.start_block is None else int(spec.start_block)
                    logs = self.explorer.get_logs(source, spec.event.topic0, start, block)
                    change = replay_latest(logs, lambda log, s=spec: s.event.decode(log)[s.arg])
                value = change.value if change else None
                resolved[spec.name] = value
                self.expected[(token.address, spec.name)] = value
                if value is not None and not is_zero(value):
                    holders.append(self.holder(token, spec.name, value, change.block, change.tx))
            self.resolved[token.address] = resolved
        return holders

    def validate(self, holders: list[RoleHolder], block: int) -> None:
        by_key = {(item.token, item.role): item for item in holders}
        for token in self.tokens:
            resolved = self.resolved[token.address]
            for spec in self.role_specs:
                target = spec.address(token, resolved)
                if spec.reader is None or target is None or is_zero(target):
                    continue
                expected = self.expected[(token.address, spec.name)]
                actual = spec.reader.read(self.rpc, target, block)
                match = same_address(expected, actual) or (is_zero(expected) and is_zero(actual))
                item = by_key.get((token.address, spec.name))
                if item is not None:
                    item.validated = match
                    if not match:
                        item.note = f"on-chain value is {actual}"
                elif not match:
                    self.notes.append(
                        f"{token.stock} {spec.name}: no holder in the logs, but the on-chain value is {actual}."
                    )
