# HA Simple MCP Usage Guide (English)

## What this component provides

`ha_simple_mcp` is a Home Assistant custom integration (HACS-ready) that exposes
Home Assistant REST API routes as MCP tools.

It automatically:

- Discovers `/api/**` endpoints from HA runtime.
- Builds MCP tool schema (name, description, params, required fields, returns).
- Validates incoming MCP arguments.
- Proxies tool calls to HA API.
- Supports auth token, read-only mode, and scope filtering.
- Caches generated tool schema with TTL.

## Endpoints exposed by MCP server

- `GET /health`
- `GET /mcp/tools`
- `POST /mcp/call`

## Setup in Home Assistant

1. Place integration files into:
   `custom_components/ha_simple_mcp/`
2. Restart Home Assistant.
3. Add integration from UI.
4. Fill settings:
   - Listen host (empty = all interfaces)
   - Listen port
   - Optional auth token
   - HA API user
   - Read-only mode
   - Scope allowlist
   - Schema cache TTL
   - API timeout

## MCP call format

```json
{
  "tool": "ha_get_api_states_entity_id",
  "arguments": {
    "entity_id": "light.kitchen"
  },
  "scopes": ["ha.api.get.*"]
}
```

## Development

Install dependencies:

```bash
python3 -m pip install -r requirements-dev.txt
```

Run tests:

```bash
python3 -m pytest -q
```
