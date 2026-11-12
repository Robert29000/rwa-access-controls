from rwa_access.core.classify import AddressClassifier

DELEGATE = "5a7fc11397e9a8ad41bf10bf13f22b0a63f96f6d"
CODE = {
    "0x" + "01" * 20: "0x",  # EOA
    "0x" + "02" * 20: "0xef0100" + DELEGATE,  # EIP-7702 delegated EOA
    "0x" + "03" * 20: "0x6080604052",  # verified contract
    "0x" + "04" * 20: "0x6080604052",  # unverified contract
}


class FakeRpc:
    def get_code(self, address, block):
        return CODE[address]


class FakeExplorer:
    def is_verified(self, address):
        return address == "0x" + "03" * 20


def test_classify_address_types():
    classifier = AddressClassifier(FakeRpc(), FakeExplorer())
    infos = [classifier.classify(address, 1) for address in CODE]

    assert [info.label for info in infos] == [
        "EOA",
        "EOA (EIP-7702)",
        "Contract (verified)",
        "Contract (not verified)",
    ]
    assert infos[1].delegate.lower() == "0x" + DELEGATE
