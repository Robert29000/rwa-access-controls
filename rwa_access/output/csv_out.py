import csv
from pathlib import Path

from rwa_access.core.models import ProviderResult

ROLE_FIELDS = [
    "provider", "chain_id", "snapshot_block", "stock", "token_symbol", "token", "role", "holder",
    "holder_type", "delegate", "last_change_block", "last_change_tx", "validated", "note",
]
ADDRESS_FIELDS = ["provider", "chain_id", "address", "holder_type", "delegate", "roles"]


def write_csv(results: list[ProviderResult], out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    roles_path = out_dir / "role_assignments.csv"
    addresses_path = out_dir / "addresses.csv"

    with roles_path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=ROLE_FIELDS)
        writer.writeheader()
        for result in results:
            symbols = {token.address: token.symbol for token in result.tokens}
            for item in result.holders:
                info = result.addresses[item.holder]
                writer.writerow({
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
                })

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
                writer.writerow({
                    "provider": result.provider,
                    "chain_id": result.chain_id,
                    "address": address,
                    "holder_type": info.label,
                    "delegate": info.delegate or "",
                    "roles": ";".join(roles_by_address.get(address, [])),
                })
    return [roles_path, addresses_path]
