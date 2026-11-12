"""Minimal JSON-RPC client for the reads this tool needs."""

from rwa_access.http import RateLimitedSession


class RpcError(RuntimeError):
    pass


class RpcClient:
    def __init__(self, url: str, session: RateLimitedSession):
        self.url = url
        self.session = session
        self._id = 0

    def call(self, method: str, params: list):
        self._id += 1
        body = self.session.post_json(
            self.url, {"jsonrpc": "2.0", "id": self._id, "method": method, "params": params}
        )
        if "error" in body:
            raise RpcError(f"{method}: {body['error']}")
        return body["result"]

    def block_number(self) -> int:
        return int(self.call("eth_blockNumber", []), 16)

    def eth_call(self, to: str, data: str, block: int) -> str:
        return self.call("eth_call", [{"to": to, "data": data}, hex(block)])

    def get_code(self, address: str, block: int) -> str:
        return self.call("eth_getCode", [address, hex(block)])

    def get_storage_at(self, address: str, slot: str, block: int) -> str:
        return self.call("eth_getStorageAt", [address, slot, hex(block)])
