"""Proxy detection from on-chain storage.

Supported proxy types:
  - ERC-1967: implementation in the EIP-1967 implementation slot. Covers
    TransparentUpgradeableProxy, UUPS (ERC1967Proxy) and similar proxies.
    The admin slot is read too (set for transparent proxies).
  - ERC-1967 beacon: beacon in the EIP-1967 beacon slot. The implementation
    comes from beacon.implementation().

To support a new type, write a ProxyDetector subclass and add it to
default_detectors().
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from rwa_access.clients.rpc import RpcError
from rwa_access.core.abi import Abi, AbiStore
from rwa_access.core.reads import STORAGE_SLOTS
from rwa_access.evm import is_zero, word_to_address


@dataclass(frozen=True)
class DetectedProxy:
    proxy_type: str
    implementation: str | None
    admin: str | None = None
    beacon: str | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)


class ProxyDetector(ABC):
    @abstractmethod
    def detect(self, rpc, address: str, block: int) -> DetectedProxy | None:
        """Return proxy data, or None if the contract is not this type of proxy."""


def _slot_address(rpc, address: str, slot: str, block: int) -> str | None:
    value = word_to_address(rpc.get_storage_at(address, STORAGE_SLOTS[slot], block))
    return None if is_zero(value) else value


class Erc1967Detector(ProxyDetector):
    def __init__(self, beacon_abi: Abi):
        self.beacon_implementation = beacon_abi.function("implementation")

    def detect(self, rpc, address: str, block: int) -> DetectedProxy | None:
        implementation = _slot_address(rpc, address, "eip1967.implementation", block)
        if implementation:
            admin = _slot_address(rpc, address, "eip1967.admin", block)
            return DetectedProxy("ERC-1967", implementation, admin=admin)

        beacon = _slot_address(rpc, address, "eip1967.beacon", block)
        if beacon:
            fn = self.beacon_implementation
            try:
                implementation = fn.decode(rpc.eth_call(beacon, fn.encode(), block))[0]
            except (RpcError, ValueError) as exc:
                return DetectedProxy(
                    "ERC-1967 beacon", None, beacon=beacon,
                    notes=(f"beacon.implementation() failed: {exc}",),
                )
            return DetectedProxy("ERC-1967 beacon", implementation, beacon=beacon)
        return None


def default_detectors(abis: AbiStore) -> list[ProxyDetector]:
    return [Erc1967Detector(abis.get("openzeppelin/IBeacon.json"))]
