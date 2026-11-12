"""Explorer clients. Etherscan and Blockscout both expose the Etherscan-style
`module=logs&action=getLogs` endpoint, so log paging lives in one base class.
"""

from abc import ABC, abstractmethod

from rwa_access.core.models import ContractMeta, Log
from rwa_access.http import RateLimitedSession

PAGE_SIZE = 1000  # Both explorers return at most 1000 logs per call
EMPTY_MESSAGES = ("no records found", "no logs found")


class Explorer(ABC):
    def __init__(self, session: RateLimitedSession):
        self.session = session
        self._log_cache: dict[tuple, list[Log]] = {}
        self._meta_cache: dict[str, ContractMeta] = {}

    # --- logs -------------------------------------------------------------
    @property
    @abstractmethod
    def logs_url(self) -> str: ...

    def logs_params(self) -> dict:
        """Extra query params (api key, chain id) for the getLogs call."""
        return {}

    def get_logs(self, address: str, topic0: str, from_block: int, to_block: int) -> list[Log]:
        """All logs for (address, topic0) in [from_block, to_block], sorted.

        The explorers cap one response at 1000 logs and do not page reliably.
        To get more, the next call starts at the last block of the previous
        response. Duplicates are removed by (tx hash, log index).
        """
        key = (address.lower(), topic0, from_block, to_block)
        if key in self._log_cache:
            return self._log_cache[key]
        seen: dict[tuple[str, int], Log] = {}
        start = from_block
        while True:
            page = self._fetch_logs(address, topic0, start, to_block)
            for item in page:
                seen[(item.tx_hash, item.log_index)] = item
            if len(page) < PAGE_SIZE:
                break
            last_block = max(item.block_number for item in page)
            if last_block == start:
                raise RuntimeError(f"More than {PAGE_SIZE} logs in block {start} for {address}")
            start = last_block
        logs = sorted(seen.values(), key=lambda item: item.sort_key)
        self._log_cache[key] = logs
        return logs

    def _fetch_logs(self, address: str, topic0: str, from_block: int, to_block: int) -> list[Log]:
        params = {
            "module": "logs",
            "action": "getLogs",
            "address": address,
            "topic0": topic0,
            "fromBlock": from_block,
            "toBlock": to_block,
            "page": 1,
            "offset": PAGE_SIZE,
            **self.logs_params(),
        }
        body = self.session.get_json(self.logs_url, params)
        if body.get("status") != "1":
            message = str(body.get("message", "")).lower()
            if body.get("result") == [] or any(m in message for m in EMPTY_MESSAGES):
                return []
            raise RuntimeError(f"getLogs failed for {address}: {body}")
        return [_parse_log(item) for item in body["result"]]

    # --- contract metadata --------------------------------------------------
    def contract_info(self, address: str) -> ContractMeta:
        """Verified status, contract name and the explorer's proxy data (one call, cached)."""
        key = address.lower()
        if key not in self._meta_cache:
            self._meta_cache[key] = self._contract_info(address)
        return self._meta_cache[key]

    def is_verified(self, address: str) -> bool:
        return self.contract_info(address).verified

    @abstractmethod
    def _contract_info(self, address: str) -> ContractMeta: ...


def _parse_log(item: dict) -> Log:
    return Log(
        address=item["address"],
        topics=tuple(t for t in item["topics"] if t),
        data=item.get("data") or "0x",
        block_number=_to_int(item["blockNumber"]),
        log_index=_to_int(item.get("logIndex") or "0"),
        tx_hash=item["transactionHash"],
    )


def _to_int(value: str | int) -> int:
    if isinstance(value, int):
        return value
    return int(value, 16) if value.startswith("0x") else int(value)
