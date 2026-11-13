"""Framework name -> provider class.

The `framework` key of a provider file (or of an extra module) selects the class:
  - a key in FRAMEWORKS, or
  - "package.module:ClassName" for a custom StockProvider subclass.
"""

import importlib

from rwa_access.providers.access_control import AccessControlProvider
from rwa_access.providers.base import StockProvider
from rwa_access.providers.storage_roles import StorageRoleProvider

FRAMEWORKS: dict[str, type[StockProvider]] = {
    "access_control": AccessControlProvider,
    "single_address_roles": StorageRoleProvider,
}


def provider_class(framework: str) -> type[StockProvider]:
    if framework in FRAMEWORKS:
        return FRAMEWORKS[framework]
    if ":" in framework:
        module, name = framework.split(":", 1)
        return getattr(importlib.import_module(module), name)
    raise KeyError(f"framework '{framework}' (known: {', '.join(FRAMEWORKS)})")
