"""Load providers from config/providers/*.yaml.

The `framework` key of a provider file selects the provider class:
  - a key in FRAMEWORKS, or
  - "package.module:ClassName" for a custom StockProvider subclass.
"""

import importlib
from pathlib import Path

from rwa_access.config import ConfigError, load_chains, load_yaml
from rwa_access.core.abi import AbiError, AbiStore
from rwa_access.providers.access_control import AccessControlProvider
from rwa_access.providers.base import ProviderConfig, StockProvider
from rwa_access.providers.storage_roles import StorageRoleProvider

FRAMEWORKS: dict[str, type[StockProvider]] = {
    "access_control": AccessControlProvider,
    "single_address_roles": StorageRoleProvider,
}


def _provider_class(framework: str) -> type[StockProvider]:
    if framework in FRAMEWORKS:
        return FRAMEWORKS[framework]
    if ":" in framework:
        module, name = framework.split(":", 1)
        return getattr(importlib.import_module(module), name)
    raise KeyError(f"framework '{framework}' (known: {', '.join(FRAMEWORKS)})")


def load_providers(config_dir: Path, abi_dir: Path) -> dict[str, StockProvider]:
    """Return {file name without extension: provider}, sorted by file name."""
    chains = load_chains(config_dir / "chains.yaml")
    abis = AbiStore(abi_dir)
    providers: dict[str, StockProvider] = {}
    for path in sorted((config_dir / "providers").glob("*.y*ml")):
        raw = load_yaml(path)
        try:
            config = ProviderConfig.from_yaml(path.stem, raw, chains, abis, path)
            providers[path.stem] = _provider_class(raw["framework"])(config)
        except (KeyError, AbiError, ValueError, TypeError) as exc:
            raise ConfigError(f"{path}: {type(exc).__name__}: {exc}") from exc
    return providers
