from rwa_access.core.models import AddressInfo, ProviderResult, RoleHolder, Token
from rwa_access.output.markdown import provider_section

A = "0x" + "aa" * 20
B = "0x" + "bb" * 20


def test_provider_section_tables():
    tokens = [Token("AAPL", "AAPLx", "0x1"), Token("TSLA", "TSLAx", "0x2")]
    holders = [
        RoleHolder("P", 1, "AAPL", "0x1", "owner", A, validated=True),
        RoleHolder("P", 1, "TSLA", "0x2", "owner", A, validated=True),
        RoleHolder("P", 1, "AAPL", "0x1", "minter", B, validated=False),
    ]
    result = ProviderResult(
        provider="P",
        chain_name="Ethereum",
        chain_id=1,
        address_url="https://x/{address}",
        snapshot_block=100,
        tokens=tokens,
        roles=["owner", "minter", "pauser"],
        holders=holders,
        addresses={A: AddressInfo(A, "Contract", verified=True), B: AddressInfo(B, "EOA")},
    )
    text = "\n".join(provider_section(result))

    # Table 1: role rows x stock columns. Empty cells show a dash.
    assert "| Role | AAPL | TSLA |" in text
    assert f"| owner | {A} | {A} |" in text
    assert f"| minter | {B} (not validated) | — |" in text
    assert "| pauser | — | — |" in text
    # Table 2: one row per address. The stock list shows a partial scope.
    assert f"| [{A}](https://x/{A}) | owner | Contract (verified) | — |" in text
    assert f"| [{B}](https://x/{B}) | minter (AAPL) | EOA | — |" in text
    assert "2 of 3 role assignments agree" in text
