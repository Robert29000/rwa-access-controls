"""Classify an address: EOA, EIP-7702 delegated EOA, or contract.

For a contract, also get the explorer data (verified status, name) and
detect a supported proxy. For a proxy, classify its implementation too.
"""

from dataclasses import replace

from rwa_access.core.models import AddressInfo, ProxyInfo
from rwa_access.evm import same_address, to_checksum

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
    def __init__(self, rpc, explorer, proxy_detectors=()):
        self.rpc = rpc
        self.explorer = explorer
        self.proxy_detectors = list(proxy_detectors)
        self._basic_cache: dict[str, AddressInfo] = {}
        self._cache: dict[str, AddressInfo] = {}

    def _basic(self, address: str, block: int) -> AddressInfo:
        """Code type, plus verified status and name for a contract. No proxy detection."""
        key = address.lower()
        if key not in self._basic_cache:
            kind, delegate = classify_code(self.rpc.get_code(address, block))
            verified = name = None
            if kind == "Contract":
                meta = self.explorer.contract_info(address)
                verified, name = meta.verified, meta.name
            self._basic_cache[key] = AddressInfo(to_checksum(address), kind, verified, delegate, name)
        return self._basic_cache[key]

    def classify(self, address: str, block: int) -> AddressInfo:
        key = address.lower()
        if key not in self._cache:
            info = self._basic(address, block)
            if info.kind == "Contract":
                info = self._with_proxy(info, block)
            self._cache[key] = info
        return self._cache[key]

    def _with_proxy(self, info: AddressInfo, block: int) -> AddressInfo:
        meta = self.explorer.contract_info(info.address)
        for detector in self.proxy_detectors:
            found = detector.detect(self.rpc, info.address, block)
            if found is None:
                continue
            notes = list(found.notes)
            implementation = None
            if found.implementation:
                implementation = self._basic(found.implementation, block)
                if implementation.kind != "Contract":
                    notes.append(f"The implementation {implementation.address} has no contract code.")
                if meta.implementation and not same_address(meta.implementation, found.implementation):
                    notes.append(
                        f"The explorer shows the implementation {meta.implementation}. "
                        f"The storage slot shows {found.implementation}."
                    )
            proxy = ProxyInfo(found.proxy_type, implementation, found.admin, found.beacon, tuple(notes))
            return replace(info, proxy=proxy)

        if meta.proxy_type:
            target = f", implementation {meta.implementation}" if meta.implementation else ""
            note = (
                f"The explorer marks this contract as a proxy (type: {meta.proxy_type}{target}). "
                "The tool does not support this proxy type."
            )
            return replace(info, notes=(*info.notes, note))
        return info
