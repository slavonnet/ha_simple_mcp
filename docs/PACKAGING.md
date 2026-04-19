# Packaging and release model

This repository ships **two artifacts from one codebase**:

1. Home Assistant HACS custom component (`custom_components/ha_simple_mcp`)
2. Reusable Python package (`src/ha_simple_mcp`)

## Reuse strategy

- Core MCP logic lives in `src/ha_simple_mcp`:
  - endpoint catalog
  - schema generation + cache
  - validation
  - proxy
  - MCP server
- HACS integration imports core modules and adds HA-specific runtime/config flow.

## Release strategy

- HACS release: GitHub release tags consumed by HACS.
- Python package release: build and publish from same tag.

Recommended semantic versioning:

- `MAJOR`: breaking API/ABI changes
- `MINOR`: new backward-compatible features
- `PATCH`: fixes and non-breaking improvements

## Deprecation policy

- Any symbol no longer used internally must be marked with a deprecation warning first.
- Removal happens in next major version.
- CI gate includes quality tests that fail PRs on unknown public symbols.
