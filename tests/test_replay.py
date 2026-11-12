from rwa_access.config import DEFAULT_ABI_DIR
from rwa_access.core.abi import AbiStore
from rwa_access.core.models import Log
from rwa_access.core.replay import replay_access_control, replay_latest
from rwa_access.evm import to_checksum
from rwa_access.providers.access_control import role_hash

AC = AbiStore(DEFAULT_ABI_DIR).get("openzeppelin/AccessControl.json")
GRANTED, REVOKED = AC.event("RoleGranted"), AC.event("RoleRevoked")
MINTER = role_hash("MINTER_ROLE")
A = to_checksum("0x" + "aa" * 20)
B = to_checksum("0x" + "bb" * 20)


def _word(address: str) -> str:
    return "0x" + address.lower().removeprefix("0x").rjust(64, "0")


def _role_log(event, account: str, block: int, index: int = 0) -> Log:
    return Log("0xreg", (event.topic0, MINTER, _word(account), _word(B)), "0x", block, index, f"0x{block}")


def test_access_control_replay_keeps_final_holders_only():
    # The logs are out of order on purpose. The replay must sort by (block, log index).
    logs = [
        _role_log(REVOKED, A, 20),
        _role_log(GRANTED, A, 10),
        _role_log(GRANTED, B, 10, index=1),
        _role_log(GRANTED, A, 30),  # Granted again after the revoke
        _role_log(REVOKED, B, 40),
    ]
    current, revoked = replay_access_control(logs, GRANTED, REVOKED)

    assert set(current[MINTER]) == {A}
    assert current[MINTER][A].block == 30
    assert revoked == {(MINTER, B)}


def test_single_value_replay_takes_newest_event():
    logs = [
        Log("0xt", ("0xtopic", _word(A)), "0x", 5, 2, "0x2"),
        Log("0xt", ("0xtopic", _word(B)), "0x", 5, 1, "0x1"),
    ]
    change = replay_latest(logs, lambda log: to_checksum("0x" + log.topics[1][-40:]))

    assert change.value == A
    assert replay_latest([], lambda log: "") is None
