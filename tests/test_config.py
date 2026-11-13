from rwa_access.config import DEFAULT_ABI_DIR, DEFAULT_CONFIG_DIR
from rwa_access.core.models import Log
from rwa_access.providers import load_providers
from rwa_access.providers.access_control import AccessControlProvider
from rwa_access.providers.storage_roles import StorageRoleProvider


def test_shipped_configs_load_and_resolve_abis():
    # Loading builds every event, function and reader from the ABI files.
    # A wrong ABI path, event name or argument name fails here. No network is used.
    providers = load_providers(DEFAULT_CONFIG_DIR, DEFAULT_ABI_DIR)

    assert set(providers) == {"ondo", "robinhood", "xstocks"}
    assert all(len(p.tokens) == 7 for p in providers.values())

    robinhood = providers["robinhood"]
    assert isinstance(robinhood, AccessControlProvider)
    assert robinhood.hash_to_name[
        "0x9f2df0fed2c77648de5860a4cc508cd0818c85b8b8a1ab4ceeef8d981c8956a6"
    ] == "MINTER_ROLE"
    assert robinhood.granted.topic0 == "0x2f8788117e7eff1d82e926ec794901d17c78024a50270940304540a733656f0d"

    xstocks = providers["xstocks"]
    assert isinstance(xstocks, StorageRoleProvider)
    specs = {spec.name: spec for spec in xstocks.role_specs}
    assert specs["minter"].event.topic0 == "0x6adffd5c93085d835dac6f3b40adf7c242ca4b3284048d20c3d8a501748dc973"
    assert specs["minter"].reader.function.selector == "0x07546172"

    # AdminChanged has no indexed arguments. The decoder must read the data part.
    admin_changed = specs["proxyAdmin"].event
    log = Log("0x1", (admin_changed.topic0,), "0x" + "00" * 32 + "00" * 12 + "ab" * 20, 1, 0, "0x")
    assert admin_changed.decode(log)["newAdmin"].lower() == "0x" + "ab" * 20

    ondo = providers["ondo"]
    assert isinstance(ondo, AccessControlProvider) and ondo.enumerable
    assert ondo.registry_reader is None  # Each token keeps its own roles
    assert ondo.member_fn.selector == "0x9010d07c"  # From the GMToken ABI
    (minters,) = ondo.extras
    assert [t.stock for t in minters.tokens] == ["GMTokenManager", "GMIssuerManager"]
