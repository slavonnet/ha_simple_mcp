"""Compatibility wrapper re-exporting validation functions from package core.

Deprecated:
    Import from `ha_simple_mcp.validation` instead.
"""

from ha_simple_mcp.validation import ValidationError, matches_type, validate_call

__all__ = ["ValidationError", "matches_type", "validate_call"]
