import csv

from rwa_access.core.models import AddressInfo, ProviderResult, RoleHolder, Token
from rwa_access.output.csv_out import write_csv

B = "0x" + "bb" * 20


def test_extra_csv_files_use_prefix_and_contract_columns(tmp_path):
    result = ProviderResult(
        provider="Managers",
        chain_name="Ethereum",
        chain_id=1,
        address_url="https://x/{address}",
        snapshot_block=100,
        tokens=[Token("GMTokenManager", "GMTokenManager", "0x1")],
        roles=["MINTER_ROLE"],
        holders=[RoleHolder("Managers", 1, "GMTokenManager", "0x1", "MINTER_ROLE", B, validated=True)],
        addresses={B: AddressInfo(B, "EOA")},
        subject="Contract",
    )

    roles_path, addresses_path = write_csv([result], tmp_path, prefix="extra_", subject="Contract")

    assert (roles_path.name, addresses_path.name) == ("extra_role_assignments.csv", "extra_addresses.csv")
    (row,) = csv.DictReader(roles_path.open())
    assert "token_symbol" not in row and "stock" not in row
    assert (row["contract_name"], row["contract"], row["holder"]) == ("GMTokenManager", "0x1", B)
