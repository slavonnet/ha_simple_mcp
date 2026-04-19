# Packaging and release model

This repository ships one main artifact:

1. Home Assistant HACS custom component (`custom_components/ha_simple_mcp`)

and consumes reusable MCP core as an external dependency:

- Python package `ha-api-mcp` (`ha_api_mcp` import namespace)

## Reuse strategy

- Core MCP logic lives in external repository/package:
  - https://github.com/slavonnet/ha-api-mcp
- HACS integration imports `ha_api_mcp.*` modules and adds HA-specific runtime/config flow.

## Release strategy

- HACS release: GitHub release tags consumed by HACS in this repo.
- Python package release: independent in `ha-api-mcp` repository.

Recommended semantic versioning:

- `MAJOR`: breaking API/ABI changes
- `MINOR`: new backward-compatible features
- `PATCH`: fixes and non-breaking improvements

## Deprecation policy

- Any symbol no longer used internally must be marked with a deprecation warning first.
- Removal happens in next major version.
- CI gate includes quality tests that fail PRs on unknown public symbols.
