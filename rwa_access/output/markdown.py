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


def address_table(result: ProviderResult) -> list[str]:
    """Table 2: one row for each address that holds a role."""
    all_stocks = [token.stock for token in result.tokens]
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
            scope = "" if sorted(stocks) == sorted(all_stocks) else f" ({', '.join(stocks)})"
            role_text.append(role + scope)
        info = result.addresses[address]
        link = f"[{address}]({result.address_url.format(address=address)})"
        row = [link, "<br>".join(role_text), info.label, info.note or EMPTY]
        entries.append((rank(sorted_roles[0]), address.lower(), row))
    return _table(["Address", "Role", "Type", "Note"], [row for *_, row in sorted(entries)])


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
    lines += ["", "### Role holders by stock", ""]
    lines += role_matrix(result)
    lines += ["", "### Role holder addresses", ""]
    lines += address_table(result)
    lines.append("")
    return lines


HEADER = """# Access control report for tokenized stocks

Generated: {generated}.

This report shows the current role holders of each stock token. The script did these steps:

1. The script read the role events from the block explorer. It kept only the current holders.
2. The script read each role on chain with an RPC call at the snapshot block. It compared the RPC value with the value from the events.
3. The script read the code at each holder address. It set the type of each address.

Types of address:

- **EOA**: The address has no code.
- **EOA (EIP-7702)**: The address is an EOA with an EIP-7702 delegation. The "Note" column shows the delegate contract.
- **Contract (verified)**: The address has code. The explorer has the verified source code.
- **Contract (not verified)**: The address has code. The explorer does not have the verified source code.

"(not validated)" after an address means that the RPC value is different from the value in the events. Examine these addresses manually.

In the "Role" column of the address table, a stock list in parentheses shows that the address has the role only for those stocks. If there is no list, the address has the role for all stocks.
"""


def write_markdown(results: list[ProviderResult], path: Path) -> Path:
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [HEADER.format(generated=generated)]
    for result in results:
        lines += provider_section(result)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines))
    return path
