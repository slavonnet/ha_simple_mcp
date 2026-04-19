"""Quality test: ensure no unused public exports in package API."""

from __future__ import annotations

import importlib
import pkgutil
from collections.abc import Iterable

PUBLIC_MODULES = [
    "ha_api_mcp",
    "ha_api_mcp.models",
    "ha_api_mcp.catalog",
    "ha_api_mcp.schema",
    "ha_api_mcp.validation",
    "ha_api_mcp.proxy",
    "ha_api_mcp.server",
]


def _public_names(module) -> list[str]:
    """Return public symbol names exposed by module."""
    names = getattr(module, "__all__", None)
    if names is None:
        return [
            name
            for name in module.__dict__
            if not name.startswith("_")
            and (
                callable(module.__dict__[name])
                or isinstance(module.__dict__[name], type)
            )
        ]
    if not isinstance(names, Iterable):
        return []
    return [name for name in names if isinstance(name, str)]


def test_public_exports_resolve_to_real_symbols() -> None:
    """Each exported public symbol must resolve to existing module attribute."""
    for module_name in PUBLIC_MODULES:
        module = importlib.import_module(module_name)
        for public_name in _public_names(module):
            assert hasattr(module, public_name), (
                f"Public symbol '{public_name}' declared in {module_name} is missing"
            )


def test_package_modules_are_importable() -> None:
    """All package modules should be importable (no dead modules)."""
    package = importlib.import_module("ha_api_mcp")
    for module_info in pkgutil.walk_packages(package.__path__, package.__name__ + "."):
        importlib.import_module(module_info.name)
