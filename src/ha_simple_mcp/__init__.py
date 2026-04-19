"""Public package API for HA Simple MCP core."""

from .catalog import ApiCatalog, build_scope, discover_api_endpoints, extract_path_parameters
from .models import ApiEndpoint, ApiParameter, McpSettings, ToolCallResult
from .proxy import ApiProxy, ProxyError, build_request
from .schema import SchemaCache, build_tool_name, build_tools_schema
from .server import McpHttpServer, normalize_scopes
from .validation import ValidationError, matches_type, validate_call

__all__ = [
    "ApiCatalog",
    "ApiEndpoint",
    "ApiParameter",
    "ApiProxy",
    "McpHttpServer",
    "McpSettings",
    "ProxyError",
    "SchemaCache",
    "ToolCallResult",
    "ValidationError",
    "build_request",
    "build_scope",
    "build_tool_name",
    "build_tools_schema",
    "discover_api_endpoints",
    "extract_path_parameters",
    "matches_type",
    "normalize_scopes",
    "validate_call",
]
