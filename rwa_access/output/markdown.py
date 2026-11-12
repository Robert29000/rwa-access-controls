"""Markdown report. The text follows ASD-STE100 (Simplified Technical English)."""

from datetime import datetime, timezone
from pathlib import Path

from rwa_access.core.models import ProviderResult

EMPTY = "—"


def _row(cells: list[str]) -> str:
    return "| " + " | ".join(cells) + " |"


def _table(header: list[str], rows: list[list[str]]) -> list[str]:
    return [_row(header), _row(["---"] * len(header)), *(_row(r) for r in rows)]


def role_matrix(result: ProviderResult) -> list[str]:
    """Table 1: one row for each role, one column for each stock."""
    cells: dict[tuple[str, str], list[str]] = {}
    for item in result.holders:
        text = item.holder if item.validated else f"{item.holder} (not validated)"
        cells.setdefault((item.role, item.stock), []).append(text)
    stocks = [token.stock for token in result.tokens]
    rows = [
        [role, *("<br>".join(cells.get((role, stock), [])) or EMPTY for stock in stocks)]
        for role in result.roles
    ]
    return _table(["Role", *stocks], rows)


def _link(result: ProviderResult, address: str) -> str:
    return f"[{address}]({result.address_url.format(address=address)})"


def _holder_roles(result: ProviderResult) -> list[tuple[str, str]]:
    """(address, role text) for each holder, in role order.

    The role text has one role per line. A stock list in parentheses shows a role
    that the address has only for some stocks.
    """
    all_stocks = sorted(token.stock for token in result.tokens)
    stocks_by: dict[str, dict[str, list[str]]] = {}
    for item in result.holders:
        stocks_by.setdefault(item.holder, {}).setdefault(item.role, []).append(item.stock)

    order = {role: i for i, role in enumerate(result.roles)}

    def rank(role: str) -> int:
        return order.get(role, len(order))

    entries = []
    for address, roles in stocks_by.items():
        sorted_roles = sorted(roles, key=rank)
        role_text = []
        for role in sorted_roles:
            stocks = roles[role]
            scope = "" if sorted(stocks) == all_stocks else f" ({', '.join(stocks)})"
            role_text.append(role + scope)
        entries.append((rank(sorted_roles[0]), address.lower(), address, "<br>".join(role_text)))
    return [(address, text) for *_, address, text in sorted(entries)]


def address_table(result: ProviderResult) -> list[str]:
    """Table 2: one row for each address that holds a role."""
    rows = []
    for address, roles in _holder_roles(result):
        info = result.addresses[address]
        rows.append([_link(result, address), roles, info.label, info.note or EMPTY])
    return _table(["Address", "Role", "Type", "Note"], rows)


def proxy_table(result: ProviderResult) -> list[str]:
    """Table 3: one row for each role holder that is a supported proxy."""
    rows = []
    for address, roles in _holder_roles(result):
        info = result.addresses[address]
        proxy = info.proxy
        if proxy is None:
            continue
        impl = proxy.implementation
        if proxy.admin:
            control = f"Admin: {_link(result, proxy.admin)}"
        elif proxy.beacon:
            control = f"Beacon: {_link(result, proxy.beacon)}"
        else:
            control = EMPTY
        rows.append([
            _link(result, address) + (f"<br>{info.name}" if info.name else ""),
            roles,
            proxy.proxy_type,
            (_link(result, impl.address) + (f"<br>{impl.name}" if impl.name else "")) if impl else EMPTY,
            impl.label if impl else EMPTY,
            control,
            "<br>".join(proxy.notes) or EMPTY,
        ])
    if not rows:
        return ["No role holder is a supported proxy."]
    header = ["Proxy", "Role", "Proxy type", "Implementation", "Implementation type", "Admin or beacon", "Note"]
    return _table(header, rows)


def provider_section(result: ProviderResult) -> list[str]:
    total = len(result.holders)
    passed = sum(1 for item in result.holders if item.validated)
    lines = [
        f"## {result.provider}",
        "",
        f"- Chain: {result.chain_name} (chain ID {result.chain_id}).",
        f"- Snapshot block: {result.snapshot_block}.",
        f"- Validation: {passed} of {total} role assignments agree with the RPC read at the snapshot block.",
    ]
    for note in result.notes:
        lines.append(f"- Note: {note}")
    lines += ["", "### Tokens", ""]
    lines += _table(
        ["Stock", "Symbol", "Token address"],
        [[t.stock, t.symbol, f"[{t.address}]({result.address_url.format(address=t.address)})"]
         for t in result.tokens],
    )
    if result.role_hashes:
        lines += ["", "### Role hashes", ""]
        lines += role_hash_section(result)
    lines += ["", "### Role holders by stock", ""]
    lines += role_matrix(result)
    lines += ["", "### Role holder addresses", ""]
    lines += address_table(result)
    lines += ["", "### Proxy contracts", ""]
    lines += proxy_table(result)
    lines.append("")
    return lines


def role_hash_section(result: ProviderResult) -> list[str]:
    """Role name to bytes32 hash, for a manual hasRole(role, account) check on the explorer."""
    links = ", ".join(
        f"[{address}]({result.address_url.format(address=address)})" for address in result.role_registries
    )
    lines = [
        f"To examine a role on the explorer, call `hasRole(role, account)` on the role registry: {links}.",
        "",
    ]
    return lines + _table(["Role", "Hash (bytes32)"], [[n, f"`{h}`"] for n, h in result.role_hashes.items()])


HEADER = """# Access control report for tokenized stocks

Generated: {generated}.

This report shows the current role holders of each stock token. The script did these steps:

1. The script read the role events from the block explorer. It kept only the current holders.
2. The script read each role on chain with an RPC call at the snapshot block. It compared the RPC value with the value from the events.
3. The script read the code at each holder address. It set the type of each address.
4. For each contract, the script read the EIP-1967 storage slots. If the contract is an ERC-1967 proxy, the script read its implementation address. Then it read the type and the verification status of the implementation.

Types of address:

- **EOA**: The address has no code.
- **EOA (EIP-7702)**: The address is an EOA with an EIP-7702 delegation. The "Note" column shows the delegate contract.
- **Contract (verified)**: The address has code. The explorer has the verified source code.
- **Contract (not verified)**: The address has code. The explorer does not have the verified source code.

"(not validated)" after an address means that the RPC value is different from the value in the events. Examine these addresses manually.

The "Proxy contracts" table shows the role holders that are ERC-1967 proxies:

- **Proxy type**: "ERC-1967" means that the implementation is in the EIP-1967 implementation slot. "ERC-1967 beacon" means that the proxy gets the implementation from a beacon contract.
- **Admin or beacon**: The value of the EIP-1967 admin slot, or the beacon address. A dash means that the admin slot is empty. In this case, the upgrade function is usually in the implementation (UUPS).
- The contract name below an address comes from the block explorer.

The tool supports only ERC-1967 proxies. If the explorer marks a contract as a proxy of a different type, the "Note" column of the address table tells you.

Look at the "Role" column of the address and proxy tables. A stock list in parentheses shows that the address has the role only for those stocks. If there is no list, the address has the role for all stocks.
"""


def write_markdown(results: list[ProviderResult], path: Path) -> Path:
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [HEADER.format(generated=generated)]
    for result in results:
        lines += provider_section(result)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines))
    return path
