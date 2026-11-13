"""Load providers from config/providers/*.yaml.

The `framework` key of a provider file selects the provider class (see frameworks.py).
The optional `extras` list of a provider file adds extra modules (see rwa_access/extras).
"""

from pathlib import Path

from rwa_access.config import ConfigError, load_chains, load_yaml
from rwa_access.core.abi import AbiError, AbiStore
from rwa_access.providers.base import ProviderConfig, StockProvider
from rwa_access.providers.frameworks import FRAMEWORKS, provider_class

__all__ = ["FRAMEWORKS", "load_providers", "provider_class"]


def load_providers(config_dir: Path, abi_dir: Path) -> dict[str, StockProvider]:
    """Return {file name without extension: provider}, sorted by file name.

    Each provider has its extra modules in `provider.extras`.
    """
    from rwa_access.extras import load_extras  # Here: rwa_access.extras imports this package

    chains = load_chains(config_dir / "chains.yaml")
    abis = AbiStore(abi_dir)
    providers: dict[str, StockProvider] = {}
    for path in sorted((config_dir / "providers").glob("*.y*ml")):
        raw = load_yaml(path)
        try:
            config = ProviderConfig.from_yaml(path.stem, raw, chains, abis, path)
            provider = provider_class(raw["framework"])(config)
            provider.extras = load_extras(provider)
        except (KeyError, AbiError, ValueError, TypeError) as exc:
            raise ConfigError(f"{path}: {type(exc).__name__}: {exc}") from exc
        providers[path.stem] = provider
    return providers
