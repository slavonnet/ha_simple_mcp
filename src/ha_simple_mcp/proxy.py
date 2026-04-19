"""Proxy translation between MCP calls and Home Assistant REST API."""

from __future__ import annotations

from http import HTTPStatus
from typing import Any

from aiohttp import ClientSession

from .models import ApiEndpoint, McpSettings


class ProxyError(RuntimeError):
    """Raised when proxying request to Home Assistant API fails."""


class ApiProxy:
    """Translate MCP tool calls into HTTP requests to Home Assistant API.

    Args:
        settings: Runtime settings containing auth, timeout, and base URL options.

    Returns:
        ApiProxy: Configured proxy ready to call Home Assistant REST API.
    """

    def __init__(self, settings: McpSettings) -> None:
        """Initialize API proxy with runtime settings.

        Args:
            settings: Resolved runtime settings used to construct HTTP requests.
        """
        self._settings = settings

    async def call(self, endpoint: ApiEndpoint, args: dict[str, Any]) -> tuple[int, Any]:
        """Invoke one Home Assistant API endpoint.

        Args:
            endpoint: Endpoint metadata resolved by tool name.
            args: Validated tool call arguments.

        Returns:
            Tuple of `(status_code, parsed_payload)`.

        Raises:
            ProxyError: If request is blocked by read-only mode or upstream returns error.
        """
        method = endpoint.method.upper()
        if self._settings.read_only and method != "GET":
            raise ProxyError("Read-only mode blocks non-GET requests")

        url, body, query = build_request(endpoint, args)
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
                method,
                f"{self._settings.base_url}{url}",
                **request_kwargs,
            ) as response:
                try:
                    payload = await response.json(content_type=None)
                except Exception:
                    payload = await response.text()

                if response.status >= HTTPStatus.BAD_REQUEST:
                    raise ProxyError(f"HA API error {response.status}: {payload}")
                return response.status, payload


def build_request(
    endpoint: ApiEndpoint, args: dict[str, Any]
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    """Build target request path/body/query from endpoint definition.

    Args:
        endpoint: Endpoint metadata.
        args: Tool arguments validated against endpoint schema.

    Returns:
        Tuple `(path, json_body, query_params)`.
    """
    path = endpoint.path
    body: dict[str, Any] = {}
    query: dict[str, Any] = {}

    path_param_names = {
        param.name for param in endpoint.parameters if param.in_path
    }
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


_build_request = build_request
