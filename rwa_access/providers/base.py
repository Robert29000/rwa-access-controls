"""Base class for a stock provider.

A provider is one YAML file in config/providers/. The `framework` key selects
the provider class (see FRAMEWORKS in providers/__init__.py). The base class runs
the shared steps:
  1. Fix one snapshot block for the chain.
  2. collect(): read the final role holders from logs.
  3. Run the token checks from the config.
  4. validate(): compare each holder with an RPC read at the snapshot block.
  5. Classify each holder address (EOA, EIP-7702 EOA, contract + verified).
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from rwa_access.config import ChainConfig, ChainContext
from rwa_access.core.abi import AbiStore
from rwa_access.core.models import ProviderResult, RoleHolder, Token
from rwa_access.core.reads import Reader
from rwa_access.evm import same_address, to_checksum

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class TokenCheck:
    """Read a value from each token and compare it with `expect`.

    `expect` is a literal address, or a name the provider resolves for each
    token (for example "registry", or a role name).
    """

    name: str
    reader: Reader
    expect: str


@dataclass
class ProviderConfig:
    key: str  # File name without extension, used on the CLI
    name: str
    chain: ChainConfig
    tokens: list[Token]  # Stock tokens, or the contracts of an extra module
    token_checks: list[TokenCheck]
    abis: AbiStore  # Includes the aliases from the provider file
    raw: dict  # Full YAML content, for the framework section
    source: Path
    subject: str = "Stock"  # "Contract" when the config lists `contracts`, not `tokens`
    description: str = ""

    @classmethod
    def from_yaml(cls, key: str, raw: dict, chains: dict[str, ChainConfig], abis: AbiStore, source: Path):
        abis = abis.with_aliases(raw.get("abis", {}))
        if raw["chain"] not in chains:
            raise KeyError(f"chain '{raw['chain']}' (known: {', '.join(chains)})")
        if "contracts" in raw:
            # Extra module: {name, address, start_block, description}. The name is the column name.
            subject = "Contract"
            tokens = [
                Token(
                    stock=str(item["name"]),
                    symbol=str(item["name"]),
                    address=to_checksum(item["address"]),
                    start_block=int(item.get("start_block", 0)),
                    description=" ".join(str(item.get("description", "")).split()),
                )
                for item in raw["contracts"]
            ]
        else:
            subject = "Stock"
            tokens = [
                Token(
                    stock=str(item["stock"]),
                    symbol=str(item.get("symbol", item["stock"])),
                    address=to_checksum(item["address"]),
                    start_block=int(item.get("start_block", 0)),
                )
                for item in raw["tokens"]
            ]
        checks = [
            TokenCheck(item["name"], Reader.from_config(item["read"], abis), str(item["expect"]))
            for item in raw.get("token_checks", [])
        ]
        description = " ".join(str(raw.get("description", "")).split())
        return cls(
            key, raw["name"], chains[raw["chain"]], tokens, checks, abis, raw, source, subject, description
        )


class StockProvider(ABC):
    def __init__(self, config: ProviderConfig, ctx: ChainContext | None = None):
        self.config = config
        self.name = config.name
        self.chain = config.chain
        self.tokens = config.tokens
        self.ctx = ctx or ChainContext(config.chain, config.abis)
        self.notes: list[str] = []
        self.extras: list["StockProvider"] = []  # Extra modules (see rwa_access/extras)

    @property
    def rpc(self):
        return self.ctx.rpc

    @property
    def explorer(self):
        return self.ctx.explorer

    @abstractmethod
    def role_names(self) -> list[str]:
        """Row order for the role x stock table."""

    @abstractmethod
    def collect(self, block: int) -> list[RoleHolder]:
        """Return the final role holders, built from logs up to `block`."""

    @abstractmethod
    def validate(self, holders: list[RoleHolder], block: int) -> None:
        """Set `validated` and `note` on each holder with RPC reads at `block`."""

    def role_hashes(self) -> dict[str, str]:
        """Role name -> bytes32 hash. Only for frameworks with hashed roles."""
        return {}

    def role_registries(self) -> list[str]:
        """Contracts that answer hasRole(). Only for frameworks with hashed roles."""
        return []

    def context_value(self, token: Token, name: str) -> str | None:
        """Resolve a name used in `token_checks.expect`. Subclasses add names."""
        return None

    def holder(self, token: Token, role: str, address: str, block=None, tx=None) -> RoleHolder:
        return RoleHolder(
            provider=self.name,
            chain_id=self.chain.chain_id,
            stock=token.stock,
            token=token.address,
            role=role,
            holder=address,
            last_change_block=block,
            last_change_tx=tx,
        )

    def run_token_checks(self, block: int) -> dict[str, list[str]]:
        problems: dict[str, list[str]] = {token.address: [] for token in self.tokens}
        for token in self.tokens:
            for check in self.config.token_checks:
                if check.expect.startswith("0x"):
                    expected = check.expect
                else:
                    expected = self.context_value(token, check.expect)
                actual = check.reader.read(self.rpc, token.address, block)
                if not same_address(str(actual), expected):
                    problem = f"check '{check.name}' failed: {check.reader.describe()} is {actual}, expected {check.expect} ({expected})"
                    problems[token.address].append(problem)
                    self.notes.append(f"{token.stock}: {problem}.")
        return problems

    def run(self, block: int | None = None) -> ProviderResult:
        """Collect, check, validate and classify at `block` (default: the latest block)."""
        if block is None:
            block = self.rpc.block_number()
        log.info("%s: snapshot block %d on %s", self.name, block, self.chain.name)
        holders = self.collect(block)
        log.info("%s: %d role assignments from logs", self.name, len(holders))
        problems = self.run_token_checks(block)
        self.validate(holders, block)
        for item in holders:
            item.note = "; ".join(filter(None, [item.note, *problems[item.token]]))
        addresses = {}
        for item in holders:
            info = self.ctx.classifier.classify(item.holder, block)
            addresses[info.address] = info
        log.info("%s: %d unique addresses classified", self.name, len(addresses))
        return ProviderResult(
            provider=self.name,
            chain_name=self.chain.name,
            chain_id=self.chain.chain_id,
            address_url=self.chain.address_url,
            snapshot_block=block,
            tokens=list(self.tokens),
            roles=self.role_names(),
            holders=holders,
            addresses=addresses,
            notes=self.notes,
            role_hashes=self.role_hashes(),
            role_registries=self.role_registries(),
            subject=self.config.subject,
            description=self.config.description,
        )
