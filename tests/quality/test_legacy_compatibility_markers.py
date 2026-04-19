"""Quality gate for deprecated legacy compatibility wrappers.

This test ensures that temporary compatibility modules kept under
``custom_components/ha_simple_mcp`` are clearly marked as deprecated and can be
removed in a future ABI cleanup release.
"""

from __future__ import annotations

from pathlib import Path

LEGACY_WRAPPERS = [
    "catalog.py",
    "models.py",
    "proxy.py",
    "schema.py",
    "server.py",
    "validation.py",
]


def test_legacy_wrappers_are_marked_deprecated() -> None:
    """Ensure all compatibility wrappers include explicit deprecation marker."""
    base = Path("custom_components/ha_simple_mcp")
    for filename in LEGACY_WRAPPERS:
        content = (base / filename).read_text(encoding="utf-8")
        assert "Deprecated:" in content, (
            f"{filename} must contain deprecation marker in module docstring"
        )
