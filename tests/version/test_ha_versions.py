"""Version compatibility tests across Home Assistant route fixtures."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ha_simple_mcp.catalog import build_scope
from ha_simple_mcp.models import ApiEndpoint
from ha_simple_mcp.schema import build_tools_schema

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.mark.parametrize(
    ("fixture_name", "minimum_tools"),
    [
        ("ha_2025_1_routes.json", 3),
        ("ha_2025_2_routes.json", 5),
    ],
)
def test_schema_generation_for_ha_release_fixture(
    fixture_name: str,
    minimum_tools: int,
) -> None:
    """Guard tool schema generation against known HA release route snapshots."""
    fixture_path = FIXTURES_DIR / fixture_name
    routes = json.loads(fixture_path.read_text(encoding="utf-8"))

    endpoints = [
        ApiEndpoint(
            method=route["method"],
            path=route["path"],
            description=f"{fixture_name} {route['method']} {route['path']}",
            returns_description="json",
            scope=build_scope(route["method"], route["path"]),
        )
        for route in routes
    ]
    tools = build_tools_schema(endpoints)

    assert len(tools) >= minimum_tools
    assert all(tool["name"].startswith("ha_") for tool in tools)
    assert all(tool["x-ha-endpoint"]["scope"].startswith("ha.api.") for tool in tools)
