from rwa_access.clients.explorer import Explorer
from rwa_access.core.models import ContractMeta
from rwa_access.evm import to_checksum
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

    def _contract_info(self, address: str) -> ContractMeta:
        # getsourcecode gives the verified status, name and proxy data in one call.
        # For unverified code it returns status "1" with ABI "Contract source code not verified".
        body = self.session.get_json(
            self.base_url,
            {"module": "contract", "action": "getsourcecode", "address": address, **self.logs_params()},
        )
        if body.get("status") != "1" or not body.get("result"):
            raise RuntimeError(f"getsourcecode failed for {address}: {str(body)[:200]}")
        item = body["result"][0]
        implementation = item.get("Implementation") or None
        return ContractMeta(
            verified=item.get("ABI", "") != "Contract source code not verified",
            name=item.get("ContractName") or None,
            # Etherscan marks a proxy but does not give its type.
            proxy_type="proxy" if item.get("Proxy") == "1" else None,
            implementation=to_checksum(implementation) if implementation else None,
        )
