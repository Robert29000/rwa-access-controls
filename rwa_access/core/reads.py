"""On-chain readers, built from config:

  {abi: <alias or path>, function: <name>, args: [...]}   eth_call, first return value
  {storage_slot: <hex or alias>}                         eth_getStorageAt, as an address
"""

from dataclasses import dataclass

from rwa_access.core.abi import AbiStore, Function
from rwa_access.evm import keccak_hex, word_to_address


def _eip1967_slot(label: str) -> str:
    return hex(int(keccak_hex(label), 16) - 1)


STORAGE_SLOTS = {
    "eip1967.implementation": _eip1967_slot("eip1967.proxy.implementation"),
    "eip1967.admin": _eip1967_slot("eip1967.proxy.admin"),
    "eip1967.beacon": _eip1967_slot("eip1967.proxy.beacon"),
}


@dataclass(frozen=True)
class Reader:
    function: Function | None = None
    args: tuple = ()
    storage_slot: str | None = None

    @classmethod
    def from_config(cls, raw: dict, abis: AbiStore) -> "Reader":
        if "storage_slot" in raw:
            slot = str(raw["storage_slot"])
            return cls(storage_slot=STORAGE_SLOTS.get(slot, slot))
        if "function" in raw and "abi" in raw:
            fn = abis.get(raw["abi"]).function(raw["function"])
            return cls(function=fn, args=tuple(raw.get("args", ())))
        raise ValueError(f"A reader needs 'storage_slot', or 'abi' and 'function': {raw}")

    def read(self, rpc, address: str, block: int):
        if self.storage_slot is not None:
            return word_to_address(rpc.get_storage_at(address, self.storage_slot, block))
        result = rpc.eth_call(address, self.function.encode(*self.args), block)
        return self.function.decode(result)[0]

    def describe(self) -> str:
        if self.storage_slot is not None:
            return f"storage slot {self.storage_slot}"
        return f"{self.function.signature}"
