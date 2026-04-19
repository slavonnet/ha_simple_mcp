# HA Simple MCP (HACS adapter + external Python package)

Home Assistant custom component that deploys an MCP-compatible server and
bridges MCP tool calls to Home Assistant REST API endpoints.

## Features

- Automatic discovery of available `/api/*` endpoints from HA runtime
- MCP tool schema generation:
  - function name
  - description
  - parameters with required flags
  - return contract
- MCP -> HA API call translation with schema validation
- Security and control settings:
  - bind address (empty by default)
  - bind port
  - optional auth token (allow all if empty)
  - target HA user context
  - forced read-only mode (GET only)
- Scope filtering:
  - static allowlist from integration config
  - dynamic scopes from MCP request payload
- Cached tool schema (TTL-based)
- Test matrix:
  - unit tests
  - integration flow (Client -> MCP -> HA API mock)
  - version compatibility tests
  - install smoke tests

## Reusable Python package

Core MCP logic is consumed from external package `ha-api-mcp` (import namespace
`ha_api_mcp`) published from:

- https://github.com/slavonnet/ha-api-mcp
- release tag currently used here: `v1.1.1`

The HACS integration in this repository is a thin Home Assistant adapter layer.

## Quick start

1. Copy `custom_components/ha_simple_mcp` into your HA config directory.
2. Restart Home Assistant.
3. Add integration **HA Simple MCP**.
4. Configure:
   - `listen_host` (empty for all interfaces)
   - `listen_port`
   - `auth_token` (optional)
   - `ha_user`
   - `read_only`
   - `timeout`
   - `schema_cache_ttl`
   - `allowed_scopes` (comma-separated)

MCP endpoints exposed by the integration:

- `GET /health`
- `GET /mcp/tools`
- `POST /mcp/call`

## Development

```bash
python3 -m pip install -r requirements-dev.txt
python3 -m pytest -q
```

Quality gates required to merge PR:

- `ruff` linting
- tests
- **100% coverage** gate
- docstring completeness gate for package API
- dead-export gate (no unused public API without deprecation marker)

## Documentation

- Roadmap: [docs/ROADMAP.md](docs/ROADMAP.md)
- Architecture: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- Release process: [docs/RELEASE_PROCESS.md](docs/RELEASE_PROCESS.md)
- Russian guide: [docs/USAGE_RU.md](docs/USAGE_RU.md)
- English guide: [docs/USAGE_EN.md](docs/USAGE_EN.md)
- Spanish guide: [docs/USAGE_ES.md](docs/USAGE_ES.md)
