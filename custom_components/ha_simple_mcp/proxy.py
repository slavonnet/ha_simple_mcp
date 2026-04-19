"""Compatibility re-exports for HACS integration layer.

Deprecated:
    Import from `ha_simple_mcp.proxy` in new code.
"""

from ha_simple_mcp.proxy import ApiProxy, ProxyError
from ha_simple_mcp.proxy import build_request as _build_request

__all__ = ["ApiProxy", "ProxyError", "_build_request"]
