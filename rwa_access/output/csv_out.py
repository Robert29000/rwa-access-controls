import csv
from pathlib import Path

from rwa_access.core.models import ProviderResult

ROLE_FIELDS = [
    "provider", "chain_id", "snapshot_block", "stock", "token_symbol", "token", "role", "holder",
    "holder_type", "delegate", "last_change_block", "last_change_tx", "validated", "note",
]
# Extra modules (subject "Contract"): the stock columns name the contract.
CONTRACT_COLUMNS = {"stock": "contract_name", "token": "contract"}
ADDRESS_FIELDS = [
    "provider", "chain_id", "address", "holder_type", "contract_name", "delegate", "roles",
    "proxy_type", "implementation", "implementation_name", "implementation_type",
    "proxy_admin", "proxy_beacon", "note",
]


def write_csv(
    results: list[ProviderResult], out_dir: Path, prefix: str = "", subject: str = "Stock"
) -> list[Path]:
    """Write <prefix>role_assignments.csv and <prefix>addresses.csv.

    subject "Contract" (extra modules): the columns are contract_name and contract,
    not stock, token_symbol and token.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    roles_path = out_dir / f"{prefix}role_assignments.csv"
    addresses_path = out_dir / f"{prefix}addresses.csv"
    if subject == "Contract":
        role_fields = [CONTRACT_COLUMNS.get(f, f) for f in ROLE_FIELDS if f != "token_symbol"]
    else:
        role_fields = ROLE_FIELDS

    with roles_path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=role_fields)
        writer.writeheader()
        for result in results:
            symbols = {token.address: token.symbol for token in result.tokens}
            for item in result.holders:
                info = result.addresses[item.holder]
                row = {
                    "provider": item.provider,
                    "chain_id": item.chain_id,
                    "snapshot_block": result.snapshot_block,
                    "stock": item.stock,
                    "token_symbol": symbols[item.token],
                    "token": item.token,
                    "role": item.role,
                    "holder": item.holder,
                    "holder_type": info.label,
                    "delegate": info.delegate or "",
                    "last_change_block": item.last_change_block or "",
                    "last_change_tx": item.last_change_tx or "",
                    "validated": item.validated,
                    "note": item.note,
                }
                if subject == "Contract":
                    row.pop("token_symbol")
                    row = {CONTRACT_COLUMNS.get(k, k): v for k, v in row.items()}
                writer.writerow(row)

    with addresses_path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=ADDRESS_FIELDS)
        writer.writeheader()
        for result in results:
            roles_by_address: dict[str, list[str]] = {}
            for item in result.holders:
                roles = roles_by_address.setdefault(item.holder, [])
                if item.role not in roles:
                    roles.append(item.role)
            for address, info in result.addresses.items():
                proxy = info.proxy
                impl = proxy.implementation if proxy else None
                writer.writerow({
                    "provider": result.provider,
                    "chain_id": result.chain_id,
                    "address": address,
                    "holder_type": info.label,
                    "contract_name": info.name or "",
                    "delegate": info.delegate or "",
                    "roles": ";".join(roles_by_address.get(address, [])),
                    "proxy_type": proxy.proxy_type if proxy else "",
                    "implementation": impl.address if impl else "",
                    "implementation_name": (impl.name or "") if impl else "",
                    "implementation_type": impl.label if impl else "",
                    "proxy_admin": (proxy.admin or "") if proxy else "",
                    "proxy_beacon": (proxy.beacon or "") if proxy else "",
                    "note": "; ".join(filter(None, [info.note, *(proxy.notes if proxy else ())])),
                })
    return [roles_path, addresses_path]
