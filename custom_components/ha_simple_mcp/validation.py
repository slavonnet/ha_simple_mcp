"""Compatibility wrapper re-exporting validation functions from package core.

Deprecated:
    Import from `ha_api_mcp.validation` instead.
"""

from ha_api_mcp.validation import ValidationError, matches_type, validate_call

__all__ = ["ValidationError", "matches_type", "validate_call"]
