# HA Simple MCP: Guia Rapida (ES)

Este modulo HACS para Home Assistant expone herramientas MCP sobre la API REST
de HA.

## Funciones principales

- Descubre endpoints `/api/*` disponibles en tiempo de ejecucion.
- Genera un esquema de tools MCP con:
  - nombre de funcion
  - descripcion
  - parametros (tipo, descripcion, required)
  - contrato de respuesta
- Traduce llamadas MCP a llamadas REST de Home Assistant.
- Valida argumentos contra el esquema generado.
- Incluye cache TTL para esquema de tools.

## Seguridad

- `listen_host` y `listen_port` para bind.
- `auth_token` opcional (si esta vacio, acceso abierto).
- `ha_user` para identidad de API.
- `read_only`: bloquea metodos distintos de GET.
- `allowed_scopes`: allowlist de scopes (configuracion local).
- `scopes` en payload MCP para filtrado extra del lado del cliente AI.

## Endpoints MCP

- `GET /health`
- `GET /mcp/tools`
- `POST /mcp/call`

Ejemplo de llamada:

```json
{
  "tool": "ha_get_api_states_entity_id",
  "arguments": {
    "entity_id": "light.kitchen"
  },
  "scopes": ["ha.api.get.api.states*"]
}
```
