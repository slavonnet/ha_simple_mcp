"""Proxy translator between MCP and Home Assistant REST API."""

from __future__ import annotations

from http import HTTPStatus
from typing import Any

from aiohttp import ClientSession

from .models import ApiEndpoint, McpSettings


class ProxyError(RuntimeError):
    """Error raised by proxy calls."""


class ApiProxy:
    """Translate tool calls to HA REST API calls."""

    def __init__(self, settings: McpSettings) -> None:
        self._settings = settings

    async def call(self, endpoint: ApiEndpoint, args: dict[str, Any]) -> tuple[int, Any]:
        """Invoke selected HA endpoint according to endpoint metadata."""
        method = endpoint.method.upper()
        if self._settings.read_only and method != "GET":
            raise ProxyError("Read-only mode blocks non-GET requests")

        url, body, query = _build_request(endpoint, args)
        headers: dict[str, str] = {}
        if self._settings.auth_token:
            headers["Authorization"] = f"Bearer {self._settings.auth_token}"

        async with ClientSession() as session:
            request_kwargs: dict[str, Any] = {
                "headers": headers,
                "timeout": self._settings.timeout,
            }
            if method == "GET":
                request_kwargs["params"] = query
            elif body:
                request_kwargs["json"] = body

            async with session.request(
                method, f"{self._settings.base_url}{url}", **request_kwargs
            ) as response:
                try:
                    payload = await response.json(content_type=None)
                except Exception:
                    payload = await response.text()
                if response.status >= HTTPStatus.BAD_REQUEST:
                    raise ProxyError(f"HA API error {response.status}: {payload}")
                return response.status, payload


def _build_request(endpoint: ApiEndpoint, args: dict[str, Any]) -> tuple[str, dict[str, Any], dict[str, Any]]:
    """Build request path/body/query from endpoint definition."""
    path = endpoint.path
    body: dict[str, Any] = {}
    query: dict[str, Any] = {}
    path_param_names = {param.name for param in endpoint.parameters if f"{{{param.name}}}" in endpoint.path}
    for name in path_param_names:
        value = args.get(name)
        if value is not None:
            path = path.replace(f"{{{name}}}", str(value))

    for key, value in args.items():
        if key in path_param_names:
            continue
        if endpoint.method == "GET":
            query[key] = value
        else:
            body[key] = value
    return path, body, query
