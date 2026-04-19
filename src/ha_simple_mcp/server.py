"""MCP-compatible HTTP server for Home Assistant API tools.

The server exposes a small HTTP contract used by MCP clients:

- ``GET /health``: server health check
- ``GET /mcp/tools``: generated tool schema
- ``POST /mcp/call``: execute one MCP tool call proxied to HA API
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Sequence

from aiohttp import web

from .catalog import ApiCatalog
from .models import ApiEndpoint, McpSettings
from .proxy import ApiProxy, ProxyError
from .schema import SchemaCache
from .validation import ValidationError, validate_call

_LOGGER = logging.getLogger(__name__)


class McpHttpServer:
    """Expose MCP endpoints over aiohttp.

    Parameters
    ----------
    settings:
        Runtime server settings.
    catalog:
        Catalog used to discover and resolve tools.
    proxy:
        Proxy object that performs outbound HA API calls.
    schema_cache:
        TTL cache for generated tool schema.
    """

    def __init__(
        self,
        *,
        settings: McpSettings,
        catalog: ApiCatalog | _CatalogLike,
        proxy: ApiProxy,
        schema_cache: SchemaCache,
    ) -> None:
        self._settings = settings
        self._catalog = catalog
        self._proxy = proxy
        self._schema_cache = schema_cache
        self._runner: web.AppRunner | None = None
        self._site: web.TCPSite | None = None
        self._app = web.Application()
        self._app.router.add_get("/health", self._handle_health)
        self._app.router.add_get("/mcp/tools", self._handle_tools)
        self._app.router.add_post("/mcp/call", self._handle_call)

    async def start(self) -> None:
        """Start HTTP server and bind configured host/port."""
        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        self._site = web.TCPSite(
            self._runner,
            host=self._settings.bind_address,
            port=self._settings.port,
        )
        await self._site.start()
        _LOGGER.info(
            "HA Simple MCP server started on %s:%s",
            self._settings.bind_address or "0.0.0.0",
            self._settings.port,
        )

    async def stop(self) -> None:
        """Stop HTTP server and cleanup app runner resources."""
        if self._site is not None:
            await self._site.stop()
            self._site = None
        if self._runner is not None:
            await self._runner.cleanup()
            self._runner = None
        if self._site is None:
            return

    async def _handle_health(self, request: web.Request) -> web.Response:
        """Handle health endpoint request.

        Parameters
        ----------
        request:
            Incoming aiohttp request.

        Returns
        -------
        web.Response
            JSON response with health status or authorization error.
        """
        if not self._authorized(request):
            return web.json_response({"error": "unauthorized"}, status=401)
        return web.json_response({"status": "ok"})

    async def _handle_tools(self, request: web.Request) -> web.Response:
        """Handle tools listing request.

        Parameters
        ----------
        request:
            Incoming aiohttp request.

        Returns
        -------
        web.Response
            JSON response containing generated tools schema.
        """
        if not self._authorized(request):
            return web.json_response({"error": "unauthorized"}, status=401)
        tools = await self._schema_cache.get_or_build(self._catalog.discover)
        return web.json_response({"tools": tools})

    async def _handle_call(self, request: web.Request) -> web.Response:
        """Handle MCP tool call request and proxy it to HA API.

        Parameters
        ----------
        request:
            Incoming aiohttp request with JSON payload.

        Returns
        -------
        web.Response
            JSON response with proxied body/status or a structured error.
        """
        if not self._authorized(request):
            return web.json_response({"error": "unauthorized"}, status=401)

        try:
            payload = await request.json()
        except Exception:
            return web.json_response({"error": "invalid_json"}, status=400)

        tool_name = payload.get("tool")
        arguments = payload.get("arguments")
        request_scopes = normalize_scopes(payload.get("scopes"))
        if not isinstance(tool_name, str) or not isinstance(arguments, dict):
            return web.json_response(
                {"error": "tool_and_arguments_required"},
                status=400,
            )

        endpoint = await self._catalog.get_by_tool_name(tool_name)
        if endpoint is None:
            return web.json_response({"error": "unknown_tool"}, status=404)

        if not endpoint.allow_for_scope(
            self._settings.scope_allowlist, request_scopes
        ):
            return web.json_response({"error": "tool_scope_blocked"}, status=403)

        if self._settings.read_only and endpoint.method != "GET":
            return web.json_response({"error": "read_only_mode"}, status=403)

        try:
            validate_call(endpoint, arguments)
        except ValidationError as err:
            return web.json_response(
                {"error": "validation_failed", "detail": str(err)}, status=400
            )

        try:
            status, body = await self._proxy.call(endpoint, arguments)
        except ProxyError as err:
            return web.json_response({"error": "proxy_error", "detail": str(err)}, status=502)

        return web.json_response({"status": status, "body": body})

    def _authorized(self, request: web.Request) -> bool:
        """Validate auth token if configured in settings.

        Parameters
        ----------
        request:
            Incoming aiohttp request.

        Returns
        -------
        bool
            ``True`` when request is authorized.
        """
        if not self._settings.auth_token:
            return True
        token = request.headers.get("Authorization", "")
        expected = f"Bearer {self._settings.auth_token}"
        return token == expected

    @property
    def app(self) -> web.Application:
        """Return aiohttp application used by the server."""
        return self._app


def normalize_scopes(value: object) -> tuple[str, ...]:
    """Normalize request-provided scopes into tuple.

    Parameters
    ----------
    value:
        Raw payload value expected to be a sequence of strings.

    Returns
    -------
    tuple[str, ...]
        Cleaned scope list. Empty tuple when value is missing/invalid.
    """
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return ()
    scopes = [item for item in value if isinstance(item, str) and item.strip()]
    return tuple(scopes)


class _CatalogLike:
    """Typing protocol-like base for catalog instances used by server tests."""

    def discover(self) -> Awaitable[list[ApiEndpoint]]:
        """Return discoverable endpoints list.

        Returns
        -------
        Awaitable[list[ApiEndpoint]]
            Awaitable yielding discoverable endpoint objects.
        """
        raise NotImplementedError

    def get_by_tool_name(self, tool_name: str) -> Awaitable[ApiEndpoint | None]:
        """Return endpoint by tool name.

        Parameters
        ----------
        tool_name:
            Tool name to resolve.

        Returns
        -------
        Awaitable[ApiEndpoint | None]
            Awaitable yielding matching endpoint or ``None``.
        """
        raise NotImplementedError
