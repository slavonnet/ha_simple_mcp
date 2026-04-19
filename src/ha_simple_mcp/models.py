"""Data models for the reusable HA Simple MCP package."""

from __future__ import annotations

from dataclasses import dataclass, field
from fnmatch import fnmatchcase
from typing import Any


@dataclass(slots=True, frozen=True)
class ApiParameter:
    """Describe one argument supported by a discovered API endpoint.

    Args:
        name: Parameter identifier as exposed in MCP input schema.
        required: Indicates whether the parameter is mandatory.
        description: Human-readable parameter description.
        schema_type: JSON schema type for MCP validation.
        in_path: True when the parameter is a path segment.

    Returns:
        ApiParameter: Dataclass instance representing one endpoint parameter.
    """

    name: str
    required: bool
    description: str
    schema_type: str = "string"
    in_path: bool = False


def normalize_scope_list(scopes: list[str]) -> list[str]:
    """Normalize scope list by trimming and removing duplicates.

    Args:
        scopes: Raw scope values, potentially with spaces or duplicates.

    Returns:
        Sorted unique non-empty scope list.
    """
    cleaned = [scope.strip() for scope in scopes]
    return sorted({scope for scope in cleaned if scope})


@dataclass(slots=True, frozen=True)
class ApiEndpoint:
    """Represent one Home Assistant API endpoint exposed as MCP tool.

    Args:
        method: HTTP method of the endpoint.
        path: Relative API path (for example `/api/states/{entity_id}`).
        description: Endpoint description used in tool metadata.
        returns_description: Human-readable return contract description.
        parameters: Parameter metadata for endpoint invocation.
        scope: Scope identifier used by allowlist filtering.

    Returns:
        ApiEndpoint: Dataclass instance representing one discoverable endpoint.
    """

    method: str
    path: str
    description: str
    returns_description: str
    parameters: tuple[ApiParameter, ...] = field(default_factory=tuple)
    scope: str = ""

    @property
    def tool_name(self) -> str:
        """Return deterministic MCP tool name for this endpoint."""
        body = self.path.strip("/").replace("/", "_").replace("{", "").replace("}", "")
        body = body or "root"
        return f"ha_{self.method.lower()}_{body}"

    def allow_for_scope(
        self,
        config_allowlist: tuple[str, ...] | list[str],
        request_scopes: tuple[str, ...] | list[str],
    ) -> bool:
        """Return True when endpoint is allowed by static and dynamic scopes.

        Args:
            config_allowlist: Scope patterns configured in integration options.
            request_scopes: Scope patterns provided by MCP caller request.

        Returns:
            bool: True when endpoint scope passes both filters.
        """
        config_matches = (fnmatchcase(self.scope, pattern) for pattern in config_allowlist)
        if config_allowlist and not any(config_matches):
            return False

        request_matches = (fnmatchcase(self.scope, pattern) for pattern in request_scopes)
        if request_scopes and not any(request_matches):
            return False

        return True


@dataclass(slots=True, frozen=True)
class McpSettings:
    """Runtime MCP server settings.

    Args:
        bind_address: Host/IP interface the MCP HTTP server binds to.
        port: TCP port used by MCP HTTP server.
        auth_token: Optional bearer token used for incoming MCP auth.
        target_user: Selected Home Assistant user name.
        read_only: True if only GET endpoints are allowed.
        scope_allowlist: Static scope patterns configured in integration.
        schema_cache_ttl: Tools schema cache TTL in seconds.
        timeout: Upstream HA API timeout in seconds.
        base_url: Home Assistant API base URL.

    Returns:
        McpSettings: Immutable dataclass with runtime server configuration.
    """

    bind_address: str
    port: int
    auth_token: str
    target_user: str
    read_only: bool
    scope_allowlist: tuple[str, ...]
    schema_cache_ttl: int
    timeout: int
    base_url: str = ""


@dataclass(slots=True)
class ToolCallResult:
    """Return object from proxied MCP tool call.

    Args:
        status: HTTP status code returned by HA API.
        body: Decoded response payload from HA API.

    Returns:
        ToolCallResult: Dataclass with HTTP status and response payload.
    """

    status: int
    body: Any


