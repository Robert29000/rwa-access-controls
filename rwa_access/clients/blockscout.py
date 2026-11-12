from rwa_access.clients.explorer import Explorer
from rwa_access.http import RateLimitedSession


class BlockscoutExplorer(Explorer):
    """Blockscout PRO API (multichain). The base URL includes the chain id.

    Do not use per-instance hosts such as robinhoodchain.blockscout.com:
    they are behind a Cloudflare bot check.
    """

    def __init__(self, base_url: str, chain_id: int, api_key: str, session: RateLimitedSession):
        super().__init__(session)
        self.base = base_url.rstrip("/")
        self.chain_id = chain_id
        self.api_key = api_key

    @property
    def logs_url(self) -> str:
        return f"{self.base}/api"

    def logs_params(self) -> dict:
        return {"apikey": self.api_key}

    def _is_verified(self, address: str) -> bool:
        body = self.session.get_json(
            f"{self.base}/api/v2/addresses/{address}", {"apikey": self.api_key}
        )
        return bool(body.get("is_verified"))
