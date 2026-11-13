"""AccessControlEnumerable mode and extra modules. No network: fake RPC and explorer."""

from pathlib import Path

import pytest

from rwa_access.config import DEFAULT_ABI_DIR, ChainConfig, ServiceConfig
from rwa_access.core.abi import AbiStore
from rwa_access.core.models import Log
from rwa_access.evm import to_checksum
from rwa_access.extras import load_extras
from rwa_access.providers.access_control import AccessControlProvider, role_hash
from rwa_access.providers.base import ProviderConfig

ABI = AbiStore(DEFAULT_ABI_DIR).get("openzeppelin/AccessControlEnumerable.json")
GRANTED, REVOKED = ABI.event("RoleGranted"), ABI.event("RoleRevoked")
COUNT, MEMBER = ABI.function("getRoleMemberCount"), ABI.function("getRoleMember")
ADMIN, MINTER = role_hash("DEFAULT_ADMIN_ROLE"), role_hash("MINTER_ROLE")

TOKEN = to_checksum("0x" + "11" * 20)
A, B, C, D = (to_checksum("0x" + h * 20) for h in ("aa", "bb", "cc", "dd"))
SERVICE = ServiceConfig("x", "etherscan", "https://x", "X", 0.0)
CHAIN = ChainConfig("ethereum", "Ethereum", 1, SERVICE, "ethereum", SERVICE, "https://x/{address}")


def _word(value: str) -> str:
    return "0x" + value.lower().removeprefix("0x").rjust(64, "0")


def _log(event, role: str, account: str, block: int) -> Log:
    return Log(TOKEN, (event.topic0, role, _word(account), _word(C)), "0x", block, 0, f"0x{block:x}")


class FakeRpc:
    """getRoleMemberCount / getRoleMember from a {role hash: [members]} map."""

    def __init__(self, members: dict[str, list[str]]):
        self.members = members

    def eth_call(self, to: str, data: str, block: int) -> str:
        role = "0x" + data[10:74]
        if data.startswith(COUNT.selector):
            return _word(hex(len(self.members.get(role, []))))
        if data.startswith(MEMBER.selector):
            return _word(self.members[role][int(data[74:], 16)])
        raise AssertionError(f"unexpected call {data[:10]}")


class FakeExplorer:
    def __init__(self, logs: list[Log]):
        self.logs = logs
        self.calls: list[tuple[str, int]] = []

    def get_logs(self, address, topic0, start, end):
        self.calls.append((topic0, start))
        return [log for log in self.logs if log.topics[0] == topic0]


class FakeCtx:
    def __init__(self, rpc, explorer):
        self.rpc, self.explorer = rpc, explorer


def _provider(members, logs, aliases=None) -> tuple[AccessControlProvider, FakeExplorer]:
    raw = {
        "name": "P",
        "chain": "ethereum",
        "framework": "access_control",
        "abis": aliases or {},
        "access_control": {"enumerable": True, "roles": ["DEFAULT_ADMIN_ROLE", "MINTER_ROLE"]},
        "tokens": [{"stock": "AAPL", "symbol": "AAPLon", "address": TOKEN, "start_block": 7}],
    }
    config = ProviderConfig.from_yaml("p", raw, {"ethereum": CHAIN}, AbiStore(DEFAULT_ABI_DIR), Path("p.yaml"))
    explorer = FakeExplorer(logs)
    return AccessControlProvider(config, FakeCtx(FakeRpc(members), explorer)), explorer


def test_enumerable_holders_come_from_get_role_member_and_are_checked_with_events():
    other_role = role_hash("OTHER_ROLE")
    logs = [
        _log(GRANTED, ADMIN, A, 10),
        _log(GRANTED, MINTER, B, 11),
        _log(GRANTED, MINTER, C, 12),  # Only in the events: getRoleMember() does not give C
        _log(GRANTED, other_role, A, 13),  # Role that is not in the config
    ]
    # D is only in the getRoleMember() list: no grant event.
    provider, explorer = _provider({ADMIN: [A], MINTER: [B, D]}, logs)

    holders = provider.collect(100)
    provider.validate(holders, 100)

    assert [(h.role, h.holder, h.last_change_block, h.validated) for h in holders] == [
        ("DEFAULT_ADMIN_ROLE", A, 10, True),
        ("MINTER_ROLE", B, 11, True),
        ("MINTER_ROLE", D, None, False),
    ]
    assert "event replay does not" in holders[2].note
    # The token keeps its own roles: the log scan starts at the token start block.
    assert {start for _, start in explorer.calls} == {7}
    assert any(other_role in note for note in provider.notes)
    assert any(C in note and "getRoleMember() does not" in note for note in provider.notes)


def test_extra_module_uses_provider_chain_clients_and_abi_aliases():
    provider, _ = _provider({}, [], aliases={"ace": "openzeppelin/AccessControlEnumerable.json"})
    module = {
        "key": "managers",
        "name": "Managers",
        "framework": "access_control",
        "access_control": {"abi": "ace", "enumerable": True, "roles": ["MINTER_ROLE"]},
        "contracts": [{"name": "Manager", "address": A, "start_block": 5}],
    }
    provider.config.raw["extras"] = [module]

    (extra,) = load_extras(provider)

    assert extra.config.key == "p.managers"
    assert extra.config.subject == "Contract"
    assert extra.chain is CHAIN and extra.ctx is provider.ctx
    assert [(t.stock, t.address, t.start_block) for t in extra.tokens] == [("Manager", A, 5)]

    provider.config.raw["extras"] = [{**module, "chain": "robinhood"}]
    with pytest.raises(ValueError, match="'chain' is not permitted"):
        load_extras(provider)
