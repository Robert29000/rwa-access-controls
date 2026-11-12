"""Provider for tokens that use OpenZeppelin AccessControl.

The AccessControl contract can be the token itself or an external registry.
Config section (framework: access_control):

  access_control:
    abi: openzeppelin/AccessControl.json  # Needs RoleGranted, RoleRevoked, hasRole. This is the default.
    registry: {abi: ..., function: ...}   # Optional reader on the token. Default: the token itself.
    start_blocks: {<registry>: <block>}   # Optional first block to scan.
    roles:                                # Only the roles to report.
      - DEFAULT_ADMIN_ROLE                # Hash: 0x00
      - MINTER_ROLE                       # Hash: keccak256("MINTER_ROLE")
      - {name: CUSTOM, hash: "0x..."}     # Explicit hash
"""

from collections import defaultdict
from dataclasses import dataclass

from rwa_access.core.models import RoleHolder, Token
from rwa_access.core.reads import Reader
from rwa_access.core.replay import replay_access_control
from rwa_access.evm import keccak_hex
from rwa_access.providers.base import ProviderConfig, StockProvider

DEFAULT_ABI = "openzeppelin/AccessControl.json"
DEFAULT_ADMIN_ROLE = "0x" + "00" * 32


def role_hash(name: str) -> str:
    """OZ convention: DEFAULT_ADMIN_ROLE is 0x00, other roles are keccak256(name)."""
    return DEFAULT_ADMIN_ROLE if name == "DEFAULT_ADMIN_ROLE" else keccak_hex(name)


@dataclass(frozen=True)
class Role:
    name: str
    hash: str

    @classmethod
    def from_config(cls, item) -> "Role":
        if isinstance(item, str):
            return cls(item, role_hash(item))
        return cls(item["name"], str(item.get("hash") or role_hash(item["name"])).lower())


class AccessControlProvider(StockProvider):
    def __init__(self, config: ProviderConfig, ctx=None):
        super().__init__(config, ctx)
        section = config.raw["access_control"]
        abi = config.abis.get(section.get("abi", DEFAULT_ABI))
        self.granted = abi.event("RoleGranted")
        self.revoked_event = abi.event("RoleRevoked")
        self.has_role_fn = abi.function("hasRole")
        self.registry_reader = (
            Reader.from_config(section["registry"], config.abis) if "registry" in section else None
        )
        self.start_blocks = {k.lower(): int(v) for k, v in (section.get("start_blocks") or {}).items()}
        self.roles = [Role.from_config(item) for item in section["roles"]]
        self.hash_to_name = {role.hash: role.name for role in self.roles}

        self.registry_of: dict[str, str] = {}  # token address -> registry address
        self.revoked: dict[str, set[tuple[str, str]]] = {}  # registry -> revoked pairs
        self._has_role_cache: dict[tuple[str, str, str], bool] = {}

    def role_names(self) -> list[str]:
        return [role.name for role in self.roles]

    def role_hashes(self) -> dict[str, str]:
        return {role.name: role.hash for role in self.roles}

    def role_registries(self) -> list[str]:
        return list(dict.fromkeys(self.registry_of.values()))

    def context_value(self, token: Token, name: str) -> str | None:
        if name == "registry":
            return self.registry_of.get(token.address)
        return None

    def resolve_registry(self, token: Token, block: int) -> str:
        if self.registry_reader is None:
            return token.address
        return self.registry_reader.read(self.rpc, token.address, block)

    def collect(self, block: int) -> list[RoleHolder]:
        by_registry: dict[str, list[Token]] = defaultdict(list)
        for token in self.tokens:
            registry = self.resolve_registry(token, block)
            self.registry_of[token.address] = registry
            by_registry[registry].append(token)
        if len(by_registry) > 1:
            self.notes.append(f"The tokens use {len(by_registry)} different role registries.")

        holders: list[RoleHolder] = []
        for registry, tokens in by_registry.items():
            start = self.start_blocks.get(registry.lower(), 0)
            logs = self.explorer.get_logs(registry, self.granted.topic0, start, block)
            logs += self.explorer.get_logs(registry, self.revoked_event.topic0, start, block)
            current, revoked = replay_access_control(logs, self.granted, self.revoked_event)
            self.revoked[registry] = revoked
            for role, accounts in current.items():
                if role not in self.hash_to_name:
                    # Only the configured roles are reported.
                    continue
                for change in accounts.values():
                    for token in tokens:
                        holders.append(
                            self.holder(token, self.hash_to_name[role], change.value, change.block, change.tx)
                        )
            other = sorted(set(current) - set(self.hash_to_name))
            if other:
                self.notes.append(
                    f"Registry {registry} has holders for roles that are not in the config: {', '.join(other)}."
                )
        return holders

    def has_role(self, registry: str, role: str, account: str, block: int) -> bool:
        key = (registry.lower(), role, account.lower())
        if key not in self._has_role_cache:
            data = self.has_role_fn.encode(role, account)
            self._has_role_cache[key] = bool(self.has_role_fn.decode(self.rpc.eth_call(registry, data, block))[0])
        return self._has_role_cache[key]

    def validate(self, holders: list[RoleHolder], block: int) -> None:
        name_to_hash = {role.name: role.hash for role in self.roles}
        for item in holders:
            registry = self.registry_of[item.token]
            item.validated = self.has_role(registry, name_to_hash[item.role], item.holder, block)
            if not item.validated:
                item.note = "hasRole() returned false"

        for registry, pairs in self.revoked.items():
            for role, account in sorted(pairs):
                if role in self.hash_to_name and self.has_role(registry, role, account, block):
                    self.notes.append(
                        f"{account} has {self.hash_to_name[role]} on chain, but the logs show a revoke."
                    )
