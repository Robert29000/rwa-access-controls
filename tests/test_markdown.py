from rwa_access.core.models import AddressInfo, ProviderResult, ProxyInfo, RoleHolder, Token
from rwa_access.output.markdown import provider_section

A = "0x" + "aa" * 20
B = "0x" + "bb" * 20
IMPL = "0x" + "cc" * 20


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
        addresses={
            A: AddressInfo(
                A, "Contract", verified=True, name="ERC1967Proxy",
                proxy=ProxyInfo("ERC-1967", AddressInfo(IMPL, "Contract", verified=False, name="Impl")),
            ),
            B: AddressInfo(B, "EOA"),
        },
        role_hashes={"owner": "0x" + "00" * 32},
        role_registries=[A],
    )
    text = "\n".join(provider_section(result))

    # Table 1: role rows x stock columns. Empty cells show a dash.
    assert "| Role | AAPL | TSLA |" in text
    assert f"| owner | {A} | {A} |" in text
    assert f"| minter | {B} (not validated) | — |" in text
    assert "| pauser | — | — |" in text
    # Table 2: one row per address. The stock list shows a partial scope.
    assert f"| [{A}](https://x/{A}) | owner | Contract (verified) | ERC-1967 proxy |" in text
    assert f"| [{B}](https://x/{B}) | minter (AAPL) | EOA | — |" in text
    assert "2 of 3 role assignments agree" in text
    # Table 3: proxies only. The EOA holder is not in it.
    proxies = text.split("### Proxy contracts")[1]
    assert (
        f"| [{A}](https://x/{A})<br>ERC1967Proxy | owner | ERC-1967 | [{IMPL}](https://x/{IMPL})<br>Impl"
        " | Contract (not verified) | — | — |"
    ) in proxies
    assert B not in proxies
    # Role hashes table, only when the provider gives hashes.
    assert f"call `hasRole(role, account)` on the role registry: [{A}](https://x/{A})" in text
    assert f"| owner | `0x{'00' * 32}` |" in text


def test_contract_section_for_extra_modules():
    contracts = [Token("GMTokenManager", "GMTokenManager", "0x1", description="Mints tokens.")]
    result = ProviderResult(
        provider="Managers",
        chain_name="Ethereum",
        chain_id=1,
        address_url="https://x/{address}",
        snapshot_block=100,
        tokens=contracts,
        roles=["MINTER_ROLE"],
        holders=[RoleHolder("Managers", 1, "GMTokenManager", "0x1", "MINTER_ROLE", B, validated=True)],
        addresses={B: AddressInfo(B, "EOA")},
        role_hashes={"MINTER_ROLE": "0x" + "11" * 32},
        role_registries=["0x1"],
        subject="Contract",
        description="Contracts that mint the tokens.",
    )
    text = "\n".join(provider_section(result))

    assert "## Managers\n\nContracts that mint the tokens.\n" in text
    assert "### Contracts" in text and "### Tokens" not in text
    assert "| GMTokenManager | [0x1](https://x/0x1) | Mints tokens. |" in text
    assert "### Role holders by contract" in text
    assert "| Role | GMTokenManager |" in text
    # The contract keeps its own roles: no registry link list.
    assert "call `hasRole(role, account)` on the contract." in text
