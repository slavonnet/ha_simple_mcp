"""Shared fixtures for test suite."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from aiohttp import web

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))


@pytest.fixture
def event_loop():
    """Create event loop for pytest-asyncio compatibility."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def aiohttp_unused_port():
    """Provide unique TCP port allocator for aiohttp tests."""
    from aiohttp.test_utils import unused_port

    return unused_port


@pytest.fixture
def fake_hass() -> Any:
    """Build minimal fake Home Assistant object."""
    app = web.Application()

    async def _states(_request: web.Request) -> web.Response:
        return web.json_response({"ok": True})

    async def _service(_request: web.Request) -> web.Response:
        return web.json_response({"ok": True})

    app.router.add_get("/api/states", _states)
    app.router.add_post("/api/services/{domain}/{service}", _service)
    return SimpleNamespace(http=SimpleNamespace(app=app))
