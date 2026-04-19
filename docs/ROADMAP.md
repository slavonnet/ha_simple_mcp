# Roadmap

## Stage 1: Bootstrap and architecture ✅

- [x] HACS-ready custom component layout
- [x] Integration setup/teardown hooks
- [x] Config flow + user-facing translations
- [x] Constants and runtime settings model

## Stage 2: MCP core ✅

- [x] Discover Home Assistant API endpoints at runtime
- [x] Build MCP tools schema:
  - [x] Function name
  - [x] Description
  - [x] Parameter schema with required fields
  - [x] Return contract
- [x] Translate MCP tool calls into HA REST API calls
- [x] Validate payloads against generated schema

## Stage 3: Security and controls ✅

- [x] Bind address and port settings
- [x] Optional token gate (allow-all if empty)
- [x] Run-as user selector (selected HA user)
- [x] Read-only mode (GET-only)
- [x] Scope-based filtering:
  - [x] Static allowlist from integration config
  - [x] Dynamic request scopes from MCP client payload
- [x] Schema caching with TTL and invalidation

## Stage 4: Testing matrix ✅ (baseline)

- [x] Unit tests (schema, validation, catalog, proxy, server)
- [x] Consumer-flow integration test (Client -> MCP -> HA API mock)
- [x] Version compatibility tests based on HA route fixtures
- [x] Install smoke test scaffolding (docker assets + checks)

## Stage 5: Delivery quality ✅ (baseline)

- [x] CI pipeline (pytest)
- [x] PR template
- [x] Architecture and usage docs
- [x] Additional docs in multiple languages (RU, EN, ES)

## Next iterations

- [ ] Add full options flow UI for live reconfiguration
- [ ] Extend version tests with per-release contract snapshots
- [ ] Add full Docker E2E bringing up real HA container and running MCP client scenario
