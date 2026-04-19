"""Namespace package marker for Home Assistant custom components.

This file prevents type-checking tools from collapsing
``custom_components/ha_simple_mcp`` into a top-level module name.
The integration now depends on external package ``ha_api_mcp``, but package
root disambiguation for mypy is still required.
"""
