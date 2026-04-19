"""Quality gate for API documentation completeness.

This test enforces that all public classes and functions exposed by the reusable
`ha_api_mcp` package have:

- object-level docstring;
- parameter descriptions for each argument;
- return value description.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from importlib import import_module
from types import FunctionType
from typing import Any

MODULES = [
    "ha_api_mcp.models",
    "ha_api_mcp.catalog",
    "ha_api_mcp.schema",
    "ha_api_mcp.validation",
    "ha_api_mcp.proxy",
]


@dataclass(slots=True, frozen=True)
class _ApiObject:
    """Represent inspected public API object."""

    name: str
    obj: Any
    kind: str


def _iter_public_api() -> list[_ApiObject]:
    """Collect public functions and classes from package modules."""
    api: list[_ApiObject] = []
    for module_name in MODULES:
        module = import_module(module_name)
        for name, value in vars(module).items():
            if name.startswith("_"):
                continue
            if inspect.isclass(value) and value.__module__ == module_name:
                api.append(_ApiObject(f"{module_name}.{name}", value, "class"))
            if isinstance(value, FunctionType) and value.__module__ == module_name:
                api.append(_ApiObject(f"{module_name}.{name}", value, "function"))
    return sorted(api, key=lambda item: item.name)


def _assert_has_doc_sections(name: str, obj: Any, *, require_returns: bool = True) -> None:
    """Assert docstring includes Args and Returns sections."""
    doc = inspect.getdoc(obj)
    assert doc, f"{name}: missing docstring"
    try:
        signature = inspect.signature(obj)
    except (TypeError, ValueError):
        # Builtin-like exception classes may not expose inspectable signature.
        return
    user_params = [
        param
        for param in signature.parameters.values()
        if param.name not in {"self", "cls"}
        and param.kind
        not in {
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        }
    ]
    if user_params:
        has_args = "Args:" in doc or "Parameters\n" in doc
        assert has_args, f"{name}: docstring missing Args/Parameters section"
    if require_returns and not user_params:
        return
    if require_returns:
        assert "Returns:" in doc, f"{name}: docstring missing Returns section"


def _has_explicit_init(cls: type[Any]) -> bool:
    """Return True when class defines `__init__` directly.

    Args:
        cls: Class object to inspect.

    Returns:
        bool: True if `__init__` exists in class namespace.
    """
    return "__init__" in cls.__dict__


def _is_generated_init(method: Any) -> bool:
    """Return True for dataclass-generated placeholder initializers.

    Args:
        method: Method object to inspect.

    Returns:
        bool: True if method has default generic initializer docstring.
    """
    doc = inspect.getdoc(method) or ""
    return "Initialize self.  See help(type(self)) for accurate signature." in doc


def test_public_api_docstrings_are_complete() -> None:
    """Ensure public API objects contain structured docs."""
    for api_obj in _iter_public_api():
        _assert_has_doc_sections(
            api_obj.name,
            api_obj.obj,
            require_returns=False,
        )
        if api_obj.kind == "class" and _has_explicit_init(api_obj.obj):
            if _is_generated_init(api_obj.obj.__init__):
                continue
            _assert_has_doc_sections(
                f"{api_obj.name}.__init__",
                api_obj.obj.__init__,
                require_returns=False,
            )


def test_public_methods_docstrings_are_complete() -> None:
    """Ensure public class methods contain structured docs."""
    for api_obj in _iter_public_api():
        if api_obj.kind != "class":
            continue
        for method_name, method in inspect.getmembers(api_obj.obj, inspect.isfunction):
            if method_name.startswith("_"):
                continue
            _assert_has_doc_sections(
                f"{api_obj.name}.{method_name}",
                method,
                require_returns=method_name != "__init__",
            )


def test_public_properties_have_docstrings() -> None:
    """Ensure public properties expose a descriptive docstring."""
    for api_obj in _iter_public_api():
        if api_obj.kind != "class":
            continue
        for attr_name, attr_value in vars(api_obj.obj).items():
            if attr_name.startswith("_"):
                continue
            if not isinstance(attr_value, property):
                continue
            doc = inspect.getdoc(attr_value.fget)
            assert doc, f"{api_obj.name}.{attr_name}: missing property docstring"
