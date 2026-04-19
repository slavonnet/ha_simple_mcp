"""Data models used by HA Simple MCP integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from fnmatch import fnmatchcase
from typing import Any


@dataclass(slots=True, frozen=True)
class ApiParameter:
    """Parameter metadata for one API endpoint argument."""

    name: str
    required: bool
    description: str
    schema_type: str = "string"
    in_path: bool = False


@dataclass(slots=True, frozen=True)
class ApiEndpoint:
    """One Home Assistant API endpoint discoverable as MCP tool."""

    method: str
    path: str
    description: str
    returns_description: str
    parameters: tuple[ApiParameter, ...] = field(default_factory=tuple)
    scope: str = ""

    @property
    def tool_name(self) -> str:
        """Generate deterministic MCP tool name from method and path."""
        body = self.path.strip("/").replace("/", "_").replace("{", "").replace("}", "")
        if not body:
            body = "root"
        return f"ha_{self.method.lower()}_{body}"

    def allow_for_scope(
        self,
        config_allowlist: tuple[str, ...] | list[str],
        request_scopes: tuple[str, ...] | list[str],
    ) -> bool:
        """Return True if endpoint is allowed by config and request scopes."""
        if config_allowlist and not any(
            fnmatchcase(self.scope, pattern) for pattern in config_allowlist
        ):
            return False

        if request_scopes and not any(
            fnmatchcase(self.scope, pattern) for pattern in request_scopes
        ):
            return False

        return True


@dataclass(slots=True, frozen=True)
class McpSettings:
    """Runtime MCP server settings resolved from config entry."""

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
    """Normalized response from proxy call."""

    status: int
    body: Any
