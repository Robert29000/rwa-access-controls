"""Classify an address as EOA, EIP-7702 delegated EOA, or contract."""

from rwa_access.core.models import AddressInfo
from rwa_access.evm import to_checksum

EIP7702_PREFIX = "ef0100"
EIP7702_CODE_LEN = 23  # 3-byte prefix + 20-byte delegate address


def classify_code(code: str) -> tuple[str, str | None]:
    """Return (kind, delegate) from eth_getCode output.

    - Empty code: EOA.
    - Exactly 0xef0100 || address (23 bytes): EOA with an EIP-7702 delegation.
    - Any other code: contract.
    """
    raw = code.lower().removeprefix("0x")
    if not raw:
        return "EOA", None
    if len(raw) == EIP7702_CODE_LEN * 2 and raw.startswith(EIP7702_PREFIX):
        return "EOA (EIP-7702)", to_checksum("0x" + raw[len(EIP7702_PREFIX) :])
    return "Contract", None


class AddressClassifier:
    def __init__(self, rpc, explorer):
        self.rpc = rpc
        self.explorer = explorer
        self._cache: dict[str, AddressInfo] = {}

    def classify(self, address: str, block: int) -> AddressInfo:
        key = address.lower()
        if key not in self._cache:
            kind, delegate = classify_code(self.rpc.get_code(address, block))
            verified = self.explorer.is_verified(address) if kind == "Contract" else None
            self._cache[key] = AddressInfo(to_checksum(address), kind, verified, delegate)
        return self._cache[key]
