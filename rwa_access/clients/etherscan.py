from rwa_access.clients.explorer import Explorer
from rwa_access.http import RateLimitedSession


class EtherscanExplorer(Explorer):
    """Etherscan API V2. The free tier allows 3 calls/s and only some chains (chain 1 works)."""

    def __init__(self, base_url: str, chain_id: int, api_key: str, session: RateLimitedSession):
        super().__init__(session)
        self.base_url = base_url
        self.chain_id = chain_id
        self.api_key = api_key

    @property
    def logs_url(self) -> str:
        return self.base_url

    def logs_params(self) -> dict:
        return {"chainid": self.chain_id, "apikey": self.api_key}

    def _is_verified(self, address: str) -> bool:
        # getabi returns status "1" only for verified source code.
        body = self.session.get_json(
            self.base_url,
            {"module": "contract", "action": "getabi", "address": address, **self.logs_params()},
        )
        return body.get("status") == "1"
