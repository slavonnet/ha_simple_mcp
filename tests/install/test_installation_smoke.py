"""Install smoke test placeholder.

This suite is marked as docker-dependent and exercises plugin startup path.
"""

from __future__ import annotations

import pathlib

import pytest


@pytest.mark.install
def test_install_assets_exist() -> None:
    """Verify docker-based install test assets are present."""
    root = pathlib.Path(__file__).parent
    assert (root / "docker-compose.yml").exists()
    assert (root / "Dockerfile").exists()
