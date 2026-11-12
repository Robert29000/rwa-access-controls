"""Rebuild the current role state from event logs."""

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from rwa_access.core.abi import Event
from rwa_access.core.models import Log


@dataclass(frozen=True)
class Change:
    value: str
    block: int
    tx: str


def replay_access_control(
    logs: Iterable[Log], granted: Event, revoked: Event
) -> tuple[dict[str, dict[str, Change]], set[tuple[str, str]]]:
    """Replay OZ AccessControl RoleGranted / RoleRevoked events.

    Both events have the arguments `role` and `account`.
    Returns:
      - current: {role_hash: {holder: Change of the grant that is still active}}
      - revoked: {(role_hash, account)} pairs that were revoked and not granted again
    """
    current: dict[str, dict[str, Change]] = {}
    revoked_pairs: set[tuple[str, str]] = set()
    for item in sorted(logs, key=lambda log: log.sort_key):
        if item.topics[0] == granted.topic0:
            args = granted.decode(item)
            role, account = args["role"], args["account"]
            current.setdefault(role, {})[account] = Change(account, item.block_number, item.tx_hash)
            revoked_pairs.discard((role, account))
        elif item.topics[0] == revoked.topic0:
            args = revoked.decode(item)
            role, account = args["role"], args["account"]
            if current.get(role, {}).pop(account, None) is not None:
                revoked_pairs.add((role, account))
    return {role: holders for role, holders in current.items() if holders}, revoked_pairs


def replay_latest(logs: Iterable[Log], decode: Callable[[Log], str]) -> Change | None:
    """For single-value settings: the newest event holds the current value."""
    logs = list(logs)
    if not logs:
        return None
    last = max(logs, key=lambda log: log.sort_key)
    return Change(decode(last), last.block_number, last.tx_hash)
