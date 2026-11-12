from rwa_access.config import DEFAULT_ABI_DIR
from rwa_access.core.abi import AbiStore
from rwa_access.core.classify import AddressClassifier
from rwa_access.core.models import ContractMeta
from rwa_access.core.proxy import default_detectors
from rwa_access.core.reads import STORAGE_SLOTS
from rwa_access.evm import to_checksum


def addr(n: int) -> str:
    return to_checksum("0x" + f"{n:02x}" * 20)


def word(address: str) -> str:
    return "0x" + address.lower().removeprefix("0x").rjust(64, "0")


DELEGATE = "5a7fc11397e9a8ad41bf10bf13f22b0a63f96f6d"
CONTRACT = "0x6080604052"
IMPL, ADMIN, BEACON = addr(0x10), addr(0x11), addr(0x12)

CODE = {
    addr(1): "0x",  # EOA
    addr(2): "0xef0100" + DELEGATE,  # EIP-7702 delegated EOA
    addr(3): CONTRACT,  # Verified contract
    addr(4): CONTRACT,  # Unverified contract
    addr(5): CONTRACT,  # ERC-1967 proxy with admin
    addr(6): CONTRACT,  # ERC-1967 beacon proxy
    addr(7): CONTRACT,  # Explorer marks a proxy that is not ERC-1967 (for example a Safe)
    IMPL: CONTRACT,
    BEACON: CONTRACT,
}
SLOTS = {
    (addr(5), "eip1967.implementation"): IMPL,
    (addr(5), "eip1967.admin"): ADMIN,
    (addr(6), "eip1967.beacon"): BEACON,
}
META = {
    addr(3): ContractMeta(True, "Token"),
    addr(5): ContractMeta(True, "ERC1967Proxy", "eip1967", IMPL),
    addr(6): ContractMeta(True, "BeaconProxy"),
    addr(7): ContractMeta(True, "GnosisSafeProxy", "proxy", addr(0x20)),
    IMPL: ContractMeta(False),
}


class FakeRpc:
    def get_code(self, address, block):
        return CODE[to_checksum(address)]

    def get_storage_at(self, address, slot, block):
        names = {value: name for name, value in STORAGE_SLOTS.items()}
        return word(SLOTS.get((to_checksum(address), names[slot]), "0x0"))

    def eth_call(self, to, data, block):
        assert to_checksum(to) == BEACON  # Only beacon.implementation() is called
        return word(IMPL)


class FakeExplorer:
    def contract_info(self, address):
        return META.get(to_checksum(address), ContractMeta(False))


def classifier() -> AddressClassifier:
    return AddressClassifier(FakeRpc(), FakeExplorer(), default_detectors(AbiStore(DEFAULT_ABI_DIR)))


def test_classify_address_types():
    infos = [classifier().classify(addr(n), 1) for n in (1, 2, 3, 4)]

    assert [info.label for info in infos] == [
        "EOA",
        "EOA (EIP-7702)",
        "Contract (verified)",
        "Contract (not verified)",
    ]
    assert infos[1].delegate.lower() == "0x" + DELEGATE
    assert infos[2].name == "Token" and infos[2].proxy is None


def test_erc1967_proxy_detection():
    c = classifier()
    direct, beacon, safe = (c.classify(addr(n), 1) for n in (5, 6, 7))

    assert direct.proxy.proxy_type == "ERC-1967"
    assert direct.proxy.admin == ADMIN
    assert direct.proxy.implementation.address == IMPL
    assert direct.proxy.implementation.label == "Contract (not verified)"
    assert direct.proxy.notes == ()  # The explorer implementation agrees with the slot

    assert beacon.proxy.proxy_type == "ERC-1967 beacon"
    assert beacon.proxy.beacon == BEACON
    assert beacon.proxy.implementation.address == IMPL

    # A proxy type that the tool does not support: no ProxyInfo, but a note.
    assert safe.proxy is None
    assert "does not support this proxy type" in safe.note
