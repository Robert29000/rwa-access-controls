from rwa_access.clients.explorer import Explorer
from rwa_access.core.models import ContractMeta
from rwa_access.evm import to_checksum
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

    def _contract_info(self, address: str) -> ContractMeta:
        body = self.session.get_json(
            f"{self.base}/api/v2/addresses/{address}", {"apikey": self.api_key}
        )
        implementations = body.get("implementations") or []
        return ContractMeta(
            verified=bool(body.get("is_verified")),
            name=body.get("name") or None,
            proxy_type=body.get("proxy_type") or None,  # For example "eip1967", "eip1967_beacon"
            implementation=to_checksum(implementations[0]["address_hash"]) if implementations else None,
        )
