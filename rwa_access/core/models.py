from dataclasses import dataclass, field


@dataclass(frozen=True)
class Log:
    address: str
    topics: tuple[str, ...]
    data: str
    block_number: int
    log_index: int
    tx_hash: str

    @property
    def sort_key(self) -> tuple[int, int]:
        return (self.block_number, self.log_index)


@dataclass(frozen=True)
class Token:
    stock: str  # Display name of the stock column, e.g. "GOOGL"
    symbol: str  # On-chain token symbol, e.g. "GOOGLx"
    address: str
    start_block: int = 0  # First block to scan for logs (token creation)


@dataclass
class RoleHolder:
    provider: str
    chain_id: int
    stock: str
    token: str
    role: str
    holder: str
    last_change_block: int | None = None
    last_change_tx: str | None = None
    validated: bool | None = None
    note: str = ""


@dataclass(frozen=True)
class ContractMeta:
    """Contract data from the block explorer."""

    verified: bool
    name: str | None = None
    proxy_type: str | None = None  # Explorer's proxy marker, if any
    implementation: str | None = None  # Explorer's implementation, if any


@dataclass(frozen=True)
class AddressInfo:
    address: str
    kind: str  # "EOA" | "EOA (EIP-7702)" | "Contract"
    verified: bool | None = None  # Only set for contracts
    delegate: str | None = None  # Only set for EIP-7702 EOAs
    name: str | None = None  # Contract name from the explorer
    proxy: "ProxyInfo | None" = None  # Only set for supported proxies
    notes: tuple[str, ...] = ()

    @property
    def label(self) -> str:
        if self.kind == "Contract":
            return "Contract (verified)" if self.verified else "Contract (not verified)"
        return self.kind

    @property
    def note(self) -> str:
        parts = []
        if self.delegate:
            parts.append(f"EIP-7702 delegation to {self.delegate}")
        if self.proxy:
            parts.append(f"{self.proxy.proxy_type} proxy")
        parts.extend(self.notes)
        return "; ".join(parts)


@dataclass(frozen=True)
class ProxyInfo:
    proxy_type: str  # "ERC-1967" | "ERC-1967 beacon"
    implementation: AddressInfo | None  # Classified implementation contract
    admin: str | None = None  # EIP-1967 admin slot (transparent proxy)
    beacon: str | None = None  # EIP-1967 beacon slot (beacon proxy)
    notes: tuple[str, ...] = ()


@dataclass
class ProviderResult:
    provider: str
    chain_name: str
    chain_id: int
    address_url: str  # Explorer URL template with {address}
    snapshot_block: int
    tokens: list[Token]
    roles: list[str]  # Row order for the role x stock table
    holders: list[RoleHolder]
    addresses: dict[str, AddressInfo] = field(default_factory=dict)  # Key: checksum address
    notes: list[str] = field(default_factory=list)
    # Only for role-hash frameworks (AccessControl): role name -> bytes32 hash,
    # and the contracts to call hasRole() on.
    role_hashes: dict[str, str] = field(default_factory=dict)
    role_registries: list[str] = field(default_factory=list)
    # "Stock" for a provider, "Contract" for an extra module (see rwa_access/extras).
    subject: str = "Stock"
