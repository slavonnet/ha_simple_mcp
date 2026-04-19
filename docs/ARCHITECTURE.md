# Architecture

`ha_simple_mcp` is a Home Assistant custom component that exposes MCP-compatible
tool discovery and call endpoints.

## Runtime flow

1. `config_flow.py` stores integration settings:
   - bind host + port
   - optional auth token
   - selected HA user
   - read-only mode
   - static scope allowlist
   - schema cache TTL
   - proxy timeout
2. `runtime.py` builds:
   - `ApiCatalog` for route discovery
   - `SchemaCache` for generated MCP tools schema
   - `ApiProxy` for outbound REST calls
   - `McpHttpServer` with `/mcp/tools` and `/mcp/call`
3. `server.py` handles requests:
   - authorization check (if token configured)
   - tool lookup and input validation
   - optional scope restrictions from payload (`scopes`)
   - optional read-only mode enforcement
   - proxy call to HA REST API

## Tool schema format

Each discovered endpoint is converted into:

- `name` — deterministic (`ha_<method>_<path>`)
- `description`
- `inputSchema` with parameter descriptions and required list
- `returns` description
- `x-ha-endpoint` metadata (`method`, `path`, `scope`)

## Scope control model

Tool call is allowed only if both checks pass:

1. Static allowlist from integration settings (`allowed_scopes`)
2. Dynamic scopes provided by MCP client in request payload (`scopes`)

Both use wildcard matching (`fnmatch`).

## Caching

`SchemaCache` stores generated tool schema for `schema_cache_ttl` seconds and
supports explicit invalidation.
