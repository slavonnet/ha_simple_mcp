"""Docker E2E: add integration via HA UI flow API and change options."""

from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, cast

import pytest

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
_INSTALL_DIR = pathlib.Path(__file__).parent
_CONFIG_DIR = _INSTALL_DIR / ".config-e2e"
_COMPOSE_FILE = _INSTALL_DIR / "docker-compose.yml"
_HA_PORT = int(os.getenv("HA_HOST_PORT", "18123"))
_HA_BASE_URL = f"http://127.0.0.1:{_HA_PORT}"
_HA_CLIENT_ID = f"{_HA_BASE_URL}/"
_TEST_USERNAME = "cursor-e2e"
_TEST_PASSWORD = "cursor-e2e-pass"
_TEST_DISPLAY_NAME = "Cursor E2E"
_COMPOSE_PROJECT_NAME = "ha_simple_mcp_install_e2e"

SettingsPayload = dict[str, int | bool | str | list[str]]

pytestmark = pytest.mark.install


def test_ha_container_ui_add_integration_and_change_settings() -> None:
    """Boot HA container and verify add + options update through UI flow API."""
    _require_command("docker")
    _require_command("wget")

    compose_env = os.environ.copy()
    compose_env["HA_CONFIG_DIR"] = str(_CONFIG_DIR)
    compose_env["HA_HOST_PORT"] = str(_HA_PORT)
    compose_env["COMPOSE_PROJECT_NAME"] = _COMPOSE_PROJECT_NAME

    _ensure_clean_config_dir(_CONFIG_DIR)
    _run_compose(["down", "--volumes", "--remove-orphans"], env=compose_env, check=False)
    _run_compose(["up", "-d", "--build"], env=compose_env)
    try:
        _wait_until_ready(timeout_seconds=240)

        auth_code = _create_onboarding_user()
        access_token = _exchange_auth_code(auth_code)
        _finish_onboarding(access_token)

        entry_id = _create_integration_entry(access_token)
        updated = _walk_user_case_to_settings_with_wget(access_token, entry_id)

        data = cast(SettingsPayload, updated["data"])
        assert data["listen_host"] == "127.0.0.1"
        assert data["listen_port"] == 8126
        assert data["auth_token"] == "changed-token"
        assert data["ha_user"] == _TEST_DISPLAY_NAME
        assert data["read_only"] is True
        assert data["timeout"] == 22
        assert data["schema_cache_ttl"] == 900
        assert data["allowed_scopes"] == ["ha.api.get.*", "ha.api.post.*"]
    finally:
        _run_compose(["down", "--volumes", "--remove-orphans"], env=compose_env, check=False)
        _remove_dir(_CONFIG_DIR)


def _wait_until_ready(*, timeout_seconds: int) -> None:
    """Wait until Home Assistant onboarding endpoint is available."""
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            response = _http_request("GET", f"{_HA_BASE_URL}/api/onboarding", timeout=5)
            if response.status_code == 200:
                return
        except OSError:
            pass
        time.sleep(2)
    raise AssertionError("Home Assistant container did not become ready in time")


def _create_onboarding_user() -> str:
    """Create initial HA owner user and return auth code."""
    payload: dict[str, str] = {
        "client_id": _HA_CLIENT_ID,
        "name": _TEST_DISPLAY_NAME,
        "username": _TEST_USERNAME,
        "password": _TEST_PASSWORD,
        "language": "en",
    }
    response = _http_request(
        "POST",
        f"{_HA_BASE_URL}/api/onboarding/users",
        json_payload=payload,
        timeout=15,
    )
    _assert_status(response, expected=200)
    data = _json_body(response)
    assert "auth_code" in data
    return str(data["auth_code"])


def _exchange_auth_code(auth_code: str) -> str:
    """Exchange onboarding auth code for bearer access token."""
    form = {
        "grant_type": "authorization_code",
        "code": auth_code,
        "client_id": _HA_CLIENT_ID,
    }
    response = _http_request(
        "POST",
        f"{_HA_BASE_URL}/auth/token",
        form_payload=form,
        timeout=15,
    )
    _assert_status(response, expected=200)
    data = _json_body(response)
    assert "access_token" in data
    return str(data["access_token"])


def _finish_onboarding(access_token: str) -> None:
    """Complete remaining onboarding steps using bearer token."""
    headers = _auth_headers(access_token)
    core = _http_request(
        "POST",
        f"{_HA_BASE_URL}/api/onboarding/core_config",
        headers=headers,
        timeout=15,
    )
    _assert_status(core, expected=200)
    analytics = _http_request(
        "POST",
        f"{_HA_BASE_URL}/api/onboarding/analytics",
        headers=headers,
        timeout=15,
    )
    _assert_status(analytics, expected=200)
    integration_payload: dict[str, str] = {
        "client_id": _HA_CLIENT_ID,
        "redirect_uri": f"{_HA_BASE_URL}/?auth_callback=1",
    }
    integration = _http_request(
        "POST",
        f"{_HA_BASE_URL}/api/onboarding/integration",
        headers=headers,
        json_payload=integration_payload,
        timeout=15,
    )
    _assert_status(integration, expected=200)


def _create_integration_entry(access_token: str) -> str:
    """Run config flow API to create ha_simple_mcp integration entry."""
    headers = _auth_headers(access_token)
    start = _http_request(
        "POST",
        f"{_HA_BASE_URL}/api/config/config_entries/flow",
        headers=headers,
        json_payload={"handler": "ha_simple_mcp"},
        timeout=15,
    )
    _assert_status(start, expected=200)
    start_data = _json_body(start)
    flow_id = str(start_data["flow_id"])

    finish_payload = {
        "listen_host": "",
        "listen_port": 8124,
        "auth_token": "initial-token",
        "ha_user": _TEST_DISPLAY_NAME,
        "read_only": False,
        "allowed_scopes": "ha.api.get.*",
        "timeout": 15,
        "schema_cache_ttl": 300,
    }
    finish = _http_request(
        "POST",
        f"{_HA_BASE_URL}/api/config/config_entries/flow/{flow_id}",
        headers=headers,
        json_payload=finish_payload,
        timeout=15,
    )
    _assert_status(finish, expected=200)
    finish_data = _json_body(finish)
    assert finish_data["type"] == "create_entry"
    entry = finish_data["result"]
    assert entry["domain"] == "ha_simple_mcp"
    return str(entry["entry_id"])


def _update_integration_options(access_token: str, entry_id: str) -> dict[str, Any]:
    """Run options flow API to update ha_simple_mcp settings."""
    headers = _auth_headers(access_token)
    start = _http_request(
        "POST",
        f"{_HA_BASE_URL}/api/config/config_entries/options/flow",
        headers=headers,
        json_payload={"handler": entry_id},
        timeout=15,
    )
    _assert_status(start, expected=200)
    start_data = _json_body(start)
    flow_id = str(start_data["flow_id"])

    update_payload = {
        "listen_host": "127.0.0.1",
        "listen_port": 8126,
        "auth_token": "changed-token",
        "ha_user": _TEST_DISPLAY_NAME,
        "read_only": True,
        "allowed_scopes": "ha.api.get.*, ha.api.post.*",
        "timeout": 22,
        "schema_cache_ttl": 900,
    }
    finish = _http_request(
        "POST",
        f"{_HA_BASE_URL}/api/config/config_entries/options/flow/{flow_id}",
        headers=headers,
        json_payload=update_payload,
        timeout=15,
    )
    _assert_status(finish, expected=200)
    finish_data = _json_body(finish)
    assert finish_data["type"] == "create_entry"
    return finish_data


def _auth_headers(access_token: str) -> dict[str, str]:
    """Build common auth headers for HA API calls."""
    return {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }


def _walk_user_case_to_settings_with_wget(
    access_token: str,
    entry_id: str,
) -> dict[str, Any]:
    """Go from main UI to integration settings and save options via wget."""
    _assert_wget_html_page(f"{_HA_BASE_URL}/", access_token=access_token)
    _assert_wget_html_page(f"{_HA_BASE_URL}/config/dashboard", access_token=access_token)
    _assert_wget_html_page(
        f"{_HA_BASE_URL}/config/integrations/dashboard",
        access_token=access_token,
    )
    _assert_wget_html_page(
        f"{_HA_BASE_URL}/config/integrations/integration/{entry_id}",
        access_token=access_token,
    )

    entries_url = f"{_HA_BASE_URL}/api/config/config_entries/entry?domain=ha_simple_mcp"
    entries = _wget_json_request("GET", entries_url, access_token=access_token)
    entry = _find_entry_fragment(entries, entry_id=entry_id)
    if entry.get("supports_options") is not True:
        raise AssertionError(
            "Expected supports_options=true for component settings button visibility"
        )

    start = _wget_json_request(
        "POST",
        f"{_HA_BASE_URL}/api/config/config_entries/options/flow",
        access_token=access_token,
        json_payload={"handler": entry_id},
    )
    flow_id = str(start["flow_id"])

    update_payload = {
        "listen_host": "127.0.0.1",
        "listen_port": 8126,
        "auth_token": "changed-token",
        "ha_user": _TEST_DISPLAY_NAME,
        "read_only": True,
        "allowed_scopes": "ha.api.get.*, ha.api.post.*",
        "timeout": 22,
        "schema_cache_ttl": 900,
    }
    finish = _wget_json_request(
        "POST",
        f"{_HA_BASE_URL}/api/config/config_entries/options/flow/{flow_id}",
        access_token=access_token,
        json_payload=update_payload,
    )
    if finish.get("type") != "create_entry":
        raise AssertionError("Expected create_entry response from options flow")
    return finish


def _assert_wget_html_page(url: str, *, access_token: str) -> None:
    """Fetch one UI page with wget and assert basic HTML payload exists."""
    cmd = [
        "wget",
        "-q",
        "--timeout=15",
        "-O",
        "-",
        "--header",
        f"Authorization: Bearer {access_token}",
        url,
    ]
    result = _run_command(cmd)
    body = result.stdout.lower()
    if "<html" not in body and "<home-assistant" not in body:
        raise AssertionError(f"UI page at {url} does not look like HA HTML shell")


def _wget_json_request(
    method: str,
    url: str,
    *,
    access_token: str,
    json_payload: Mapping[str, Any] | None = None,
) -> Any:
    """Call one HA endpoint through wget and parse JSON response."""
    cmd = [
        "wget",
        "-q",
        "--timeout=15",
        "-O",
        "-",
        "--header",
        f"Authorization: Bearer {access_token}",
    ]
    if method == "POST":
        cmd.extend(["--header", "Content-Type: application/json"])
        body = "{}" if json_payload is None else json.dumps(json_payload)
        cmd.extend(["--post-data", body])
    elif method != "GET":
        raise AssertionError(f"Unsupported wget JSON method: {method}")
    cmd.append(url)
    result = _run_command(cmd)
    return json.loads(result.stdout)


def _find_entry_fragment(payload: Any, *, entry_id: str) -> dict[str, Any]:
    """Find one config entry object by entry_id in list payload."""
    if not isinstance(payload, list):
        raise AssertionError("Expected config entries payload to be a JSON list")
    for item in payload:
        if not isinstance(item, dict):
            continue
        if str(item.get("entry_id", "")) == entry_id:
            return item
    raise AssertionError(f"Config entry {entry_id} not found in config entries payload")


@dataclass(slots=True)
class _HttpResponse:
    status_code: int
    method: str
    url: str
    body: str


def _http_request(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    json_payload: Mapping[str, Any] | None = None,
    form_payload: Mapping[str, str] | None = None,
    timeout: int = 15,
) -> _HttpResponse:
    """Perform HTTP request via stdlib and return normalized response."""
    req_headers = dict(headers or {})
    data_bytes: bytes | None = None
    if json_payload is not None:
        req_headers.setdefault("Content-Type", "application/json")
        data_bytes = json.dumps(json_payload).encode("utf-8")
    elif form_payload is not None:
        req_headers.setdefault("Content-Type", "application/x-www-form-urlencoded")
        data_bytes = urllib.parse.urlencode(form_payload).encode("utf-8")
    request = urllib.request.Request(
        url=url,
        method=method,
        headers=req_headers,
        data=data_bytes,
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
            return _HttpResponse(
                status_code=response.getcode(),
                method=method,
                url=url,
                body=body,
            )
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        return _HttpResponse(
            status_code=error.code,
            method=method,
            url=url,
            body=body,
        )


def _json_body(response: _HttpResponse) -> dict[str, Any]:
    """Parse response body as JSON object."""
    parsed = json.loads(response.body)
    if not isinstance(parsed, dict):
        raise AssertionError(f"Expected object JSON from {response.url}, got {type(parsed)}")
    return parsed


def _assert_status(response: _HttpResponse, *, expected: int) -> None:
    """Raise detailed assertion error on unexpected HTTP status."""
    if response.status_code == expected:
        return
    raise AssertionError(
        f"Unexpected status {response.status_code} for {response.method} "
        f"{response.url}: {response.body}"
    )


def _run_compose(
    args: list[str],
    *,
    env: dict[str, str],
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Run docker compose command from install test directory."""
    cmd = ["docker", "compose", "-f", str(_COMPOSE_FILE), *args]
    try:
        result = subprocess.run(
            cmd,
            cwd=_REPO_ROOT,
            env=env,
            check=False,
            text=True,
            capture_output=True,
        )
    except FileNotFoundError as error:
        raise AssertionError("docker command is required for full install E2E test") from error
    if check and result.returncode != 0:
        raise AssertionError(
            "docker compose command failed:\n"
            f"cmd: {' '.join(cmd)}\n"
            f"exit: {result.returncode}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    return result


def _run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    """Run shell command and return output or raise detailed error."""
    try:
        result = subprocess.run(
            command,
            cwd=_REPO_ROOT,
            check=False,
            text=True,
            capture_output=True,
        )
    except FileNotFoundError as error:
        raise AssertionError(f"Command is required but not found: {command[0]}") from error
    if result.returncode != 0:
        raise AssertionError(
            "Command failed:\n"
            f"cmd: {' '.join(command)}\n"
            f"exit: {result.returncode}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    return result


def _ensure_clean_config_dir(path: pathlib.Path) -> None:
    """Create clean config directory for isolated HA instance."""
    _remove_dir(path)
    path.mkdir(parents=True, exist_ok=True)


def _remove_dir(path: pathlib.Path) -> None:
    """Remove directory recursively when it exists."""
    if not path.exists():
        return
    shutil.rmtree(path)


def _require_command(command: str) -> None:
    """Fail fast when required binary is not available."""
    if shutil.which(command) is None:
        raise AssertionError(f"Required command is missing: {command}")


