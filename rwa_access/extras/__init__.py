"""Extra modules: role reports for other contracts of a provider.

A provider file can list extra modules in `extras`. An extra module reads the
roles of contracts that are not stock tokens, for example the minter or manager
contracts of the provider. The results go to separate output files
(extra_report.md, extra_role_assignments.csv, extra_addresses.csv), not to the
main report.

Each extra module is a StockProvider. Its config has the same keys as a provider
file, with these differences:
  - `contracts` replaces `tokens`: a list of {name, address, start_block, description}.
    The `name` is the column name in the report.
  - `chain` is not permitted. The module uses the chain of the provider.
  - `abis` adds to the ABI aliases of the provider.
  - `key` (optional) is a short name for the log. Default: the list index.
  - `description` (optional) is the text under the section heading.

  extras:
    - key: managers
      name: Ondo Global Markets manager contracts
      framework: access_control          # Any framework, or package.module:ClassName
      access_control: {enumerable: true, roles: [...]}
      contracts:
        - {name: GMTokenManager, address: "0x...", start_block: 123}

The module runs at the snapshot block of its provider and uses the same RPC and
explorer clients.

To add a new kind of extra module, write a StockProvider subclass (for example in
this package) and set `framework: rwa_access.extras.<module>:<ClassName>`.
"""

from rwa_access.providers.base import ProviderConfig, StockProvider
from rwa_access.providers.frameworks import provider_class


def load_extras(provider: StockProvider) -> list[StockProvider]:
    """Build the extra modules from the `extras` list of the provider file."""
    parent = provider.config
    extras: list[StockProvider] = []
    for index, item in enumerate(parent.raw.get("extras") or []):
        if "chain" in item:
            raise ValueError(f"extras[{index}]: 'chain' is not permitted. The module uses the provider chain.")
        if "contracts" not in item:
            raise KeyError(f"extras[{index}]: 'contracts'")
        raw = {**item, "chain": parent.chain.key}
        key = f"{parent.key}.{item.get('key', index)}"
        config = ProviderConfig.from_yaml(key, raw, {parent.chain.key: parent.chain}, parent.abis, parent.source)
        extras.append(provider_class(raw["framework"])(config, provider.ctx))
    return extras
