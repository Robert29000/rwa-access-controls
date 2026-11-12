"""Small EVM helpers: keccak and address formatting. ABI encoding lives in core/abi.py."""

from eth_hash.auto import keccak


def keccak_hex(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode()
    return "0x" + keccak(data).hex()


def to_checksum(address: str) -> str:
    """EIP-55 checksum form of an address."""
    addr = address.lower().removeprefix("0x")
    digest = keccak(addr.encode()).hex()
    return "0x" + "".join(c.upper() if int(digest[i], 16) >= 8 else c for i, c in enumerate(addr))


def word_to_address(word: str) -> str:
    """Take the low 20 bytes of a 32-byte hex word (storage slot, topic)."""
    raw = word.removeprefix("0x").rjust(64, "0")
    return to_checksum("0x" + raw[-40:])


def is_zero(address: str | None) -> bool:
    return address is None or int(address, 16) == 0


def same_address(a: str | None, b: str | None) -> bool:
    if a is None or b is None:
        return a is b
    return a.lower() == b.lower()
