"""Docker E2E: install via HACS and verify integration settings UI."""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import os
import pathlib
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import aiohttp
import pytest

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
_INSTALL_DIR = pathlib.Path(__file__).parent
_CONFIG_DIR = _INSTALL_DIR / ".config-e2e"
_COMPOSE_FILE = _INSTALL_DIR / "docker-compose.yml"
_HA_PORT = int(os.getenv("HA_HOST_PORT", "18123"))
_HA_BASE_URL = f"http://127.0.0.1:{_HA_PORT}"
_HA_WS_URL = f"ws://127.0.0.1:{_HA_PORT}/api/websocket"
_HA_CLIENT_ID = f"{_HA_BASE_URL}/"
_TEST_USERNAME = "cursor-e2e"
_TEST_PASSWORD = "cursor-e2e-pass"
_TEST_DISPLAY_NAME = "Cursor E2E"
_COMPOSE_PROJECT_NAME = "ha_simple_mcp_install_e2e"
_HACS_COMPONENT_ARCHIVE_URL = "https://github.com/hacs/integration/releases/latest/download/hacs.zip"
_HACS_CUSTOM_REPOSITORY = "slavonnet/ha_simple_mcp"
_HACS_CUSTOM_REPOSITORY_URL = f"https://github.com/{_HACS_CUSTOM_REPOSITORY}"
_HACS_GITHUB_TOKEN = os.getenv("HACS_GITHUB_TOKEN", "")
_HACS_DOMAIN = "hacs"

pytestmark = pytest.mark.install


def test_ha_container_ui_add_integration_and_change_settings() -> None:
    """Run full HACS install flow and verify settings button availability."""
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
        _wait_until_onboarding_available(timeout_seconds=300)
        auth_code = _create_onboarding_user()
        access_token = _exchange_auth_code(auth_code)
        _finish_onboarding(access_token)
        _wait_until_components_loaded(access_token, timeout_seconds=300)
        container_id = _get_homeassistant_container_id(compose_env)

        _install_hacs_custom_component(container_id)
        _restart_homeassistant(compose_env)
        _wait_until_ready(timeout_seconds=240)
        _wait_until_components_loaded(access_token, timeout_seconds=300)

        _inject_hacs_config_entry(container_id, github_token=_HACS_GITHUB_TOKEN)
        _restart_homeassistant(compose_env)
        _wait_until_ready(timeout_seconds=240)
        _wait_until_components_loaded(access_token, timeout_seconds=300)

        _wait_hacs_running(access_token, timeout_seconds=300)
        repository_id = _hacs_add_custom_repository(access_token)
        _hacs_install_repository(access_token, repository_id)
        _assert_container_file_exists(
            container_id,
            "/config/custom_components/ha_simple_mcp/manifest.json",
        )

        _restart_homeassistant(compose_env)
        _wait_until_ready(timeout_seconds=240)
        _wait_until_components_loaded(access_token, timeout_seconds=300)
        _wait_hacs_running(access_token, timeout_seconds=300)

        entry_id = _create_integration_entry(access_token)
        _walk_user_case_to_settings_with_wget(access_token, entry_id)
    finally:
        _run_compose(["down", "--volumes", "--remove-orphans"], env=compose_env, check=False)
        _remove_dir(_CONFIG_DIR)


def _wait_until_ready(*, timeout_seconds: int) -> None:
    """Wait until Home Assistant HTTP API is reachable."""
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            response = _http_request("GET", f"{_HA_BASE_URL}/manifest.json", timeout=5)
            if response.status_code in (200, 401):
                return
        except OSError:
            pass
        time.sleep(2)
    raise AssertionError("Home Assistant container did not become ready in time")


def _wait_until_onboarding_available(*, timeout_seconds: int) -> None:
    """Wait until onboarding endpoint is available for first user creation."""
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            response = _http_request("GET", f"{_HA_BASE_URL}/api/onboarding", timeout=5)
            if response.status_code == 200:
                return
        except OSError:
            pass
        time.sleep(2)
    raise AssertionError("Home Assistant onboarding endpoint did not become ready in time")


def _wait_until_components_loaded(access_token: str, *, timeout_seconds: int) -> None:
    """Wait until HA has finished loading config entries after startup."""
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        entries = _fetch_config_entries(access_token)
        transient = {"setup_in_progress", "setups_in_progress", "not_loaded"}
        broken = {"setup_error", "migration_error"}

        states = [str(entry.get("state", "")) for entry in entries]
        if any(state in broken for state in states):
            raise AssertionError(f"Home Assistant entry loading failed: {states}")
        if entries and not any(state in transient for state in states):
            return
        time.sleep(2)
    raise AssertionError("Home Assistant components did not finish loading in time")


def _fetch_config_entries(access_token: str) -> list[dict[str, Any]]:
    """Fetch full config entries list."""
    response = _http_request(
        "GET",
        f"{_HA_BASE_URL}/api/config/config_entries/entry",
        headers=_auth_headers(access_token),
        timeout=15,
    )
    _assert_status(response, expected=200)
    parsed = json.loads(response.body)
    if not isinstance(parsed, list):
        raise AssertionError("Expected config entries API to return list")
    return [item for item in parsed if isinstance(item, dict)]


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


def _restart_homeassistant(compose_env: dict[str, str]) -> None:
    """Restart Home Assistant container via docker compose."""
    _run_compose(["restart", "homeassistant"], env=compose_env)


def _get_homeassistant_container_id(compose_env: dict[str, str]) -> str:
    """Get current Home Assistant container ID from compose project."""
    result = _run_compose(["ps", "-q", "homeassistant"], env=compose_env)
    container_id = result.stdout.strip()
    if not container_id:
        raise AssertionError("Could not resolve Home Assistant container id from docker compose")
    return container_id


def _install_hacs_custom_component(container_id: str) -> None:
    """Download HACS and copy custom_components/hacs into HA config."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = pathlib.Path(temp_dir)
        archive_path = temp_path / "hacs.zip"
        extract_root = temp_path / "extract"

        with urllib.request.urlopen(_HACS_COMPONENT_ARCHIVE_URL, timeout=60) as response:
            archive_path.write_bytes(response.read())
        with zipfile.ZipFile(archive_path) as zip_archive:
            zip_archive.extractall(extract_root)

        direct_hacs_dir = extract_root / "hacs"
        candidates = [direct_hacs_dir] if direct_hacs_dir.is_dir() else []
        if not candidates:
            candidates = list(extract_root.glob("**/custom_components/hacs"))
        if not candidates and (extract_root / "manifest.json").is_file():
            candidates = [extract_root]
        if not candidates:
            raise AssertionError("HACS archive does not contain hacs component directory")
        hacs_source = candidates[0]

        _run_command(
            [
                "docker",
                "exec",
                container_id,
                "sh",
                "-c",
                "rm -rf /config/custom_components/hacs && mkdir -p /config/custom_components/hacs",
            ]
        )
        _run_command(
            [
                "docker",
                "cp",
                f"{hacs_source}/.",
                f"{container_id}:/config/custom_components/hacs",
            ]
        )


def _inject_hacs_config_entry(container_id: str, *, github_token: str) -> None:
    """Inject HACS config entry into HA storage to avoid interactive OAuth flow."""
    with tempfile.TemporaryDirectory() as temp_dir:
        local_storage = pathlib.Path(temp_dir) / "core.config_entries"
        _run_command(
            [
                "docker",
                "cp",
                f"{container_id}:/config/.storage/core.config_entries",
                str(local_storage),
            ]
        )
        payload = json.loads(local_storage.read_text(encoding="utf-8"))
        data = payload.setdefault("data", {})
        entries = data.setdefault("entries", [])
        if not isinstance(entries, list):
            raise AssertionError("core.config_entries payload has unexpected entries structure")

        now = dt.datetime.now(dt.UTC).isoformat()
        existing = next(
            (
                entry
                for entry in entries
                if isinstance(entry, dict) and str(entry.get("domain", "")) == _HACS_DOMAIN
            ),
            None,
        )
        entry_id = (
            str(existing.get("entry_id", ""))
            if isinstance(existing, dict) and existing.get("entry_id")
            else f"hacs_e2e_{uuid.uuid4().hex[:12]}"
        )
        hacs_data: dict[str, str] = {}
        if github_token.strip():
            hacs_data["token"] = github_token

        hacs_entry = {
            "created_at": now,
            "data": hacs_data,
            "disabled_by": None,
            "discovery_keys": {},
            "domain": _HACS_DOMAIN,
            "entry_id": entry_id,
            "minor_version": 1,
            "modified_at": now,
            "options": {"experimental": True},
            "pref_disable_new_entities": False,
            "pref_disable_polling": False,
            "source": "user",
            "subentries": [],
            "title": "HACS",
            "unique_id": None,
            "version": 1,
        }
        if existing is None:
            entries.append(hacs_entry)
        else:
            existing.update(hacs_entry)

        local_storage.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        _run_command(
            [
                "docker",
                "cp",
                str(local_storage),
                f"{container_id}:/config/.storage/core.config_entries",
            ]
        )


def _wait_hacs_running(access_token: str, *, timeout_seconds: int) -> None:
    """Wait for HACS integration to reach running stage."""
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            info = _hacs_ws_command(access_token, {"type": "hacs/info"}, timeout_seconds=45)
        except AssertionError:
            time.sleep(2)
            continue
        if isinstance(info, dict):
            stage = str(info.get("stage", "")).lower()
            if stage == "running":
                return
        time.sleep(2)
    raise AssertionError("HACS integration did not reach running stage")


def _hacs_add_custom_repository(access_token: str) -> str:
    """Add custom repository in HACS and return discovered repository id."""
    _hacs_ws_command(
        access_token,
        {
            "type": "hacs/repositories/add",
            "repository": _HACS_CUSTOM_REPOSITORY_URL,
            "category": "integration",
        },
        timeout_seconds=180,
    )
    return _wait_hacs_repository_registered(
        access_token,
        repository_full_name=_HACS_CUSTOM_REPOSITORY,
        timeout_seconds=360,
    )


def _hacs_install_repository(access_token: str, repository_id: str) -> None:
    """Install selected repository through HACS websocket API."""
    _hacs_ws_command(
        access_token,
        {"type": "hacs/repository/download", "repository": repository_id},
        timeout_seconds=900,
    )
    _wait_hacs_repository_installed(
        access_token,
        repository_id=repository_id,
        timeout_seconds=240,
    )


def _wait_hacs_repository_registered(
    access_token: str,
    *,
    repository_full_name: str,
    timeout_seconds: int,
) -> str:
    """Poll HACS repository list until target custom repository appears."""
    deadline = time.time() + timeout_seconds
    last_known: list[str] = []
    target_name = repository_full_name.lower()
    while time.time() < deadline:
        repositories = _hacs_list_integration_repositories(access_token)
        last_known = [str(repo.get("full_name", "")) for repo in repositories]
        for repository in repositories:
            full_name = str(repository.get("full_name", "")).lower()
            if full_name != target_name:
                continue
            repository_id = repository.get("id")
            if repository_id is None:
                continue
            return str(repository_id)
        time.sleep(3)
    raise AssertionError(
        "Custom HACS repository was not registered in time. "
        f"Expected: {repository_full_name}, seen: {last_known}"
    )


def _wait_hacs_repository_installed(
    access_token: str,
    *,
    repository_id: str,
    timeout_seconds: int,
) -> None:
    """Poll HACS repository list until target repository reports installed=True."""
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        repositories = _hacs_list_integration_repositories(access_token)
        for repository in repositories:
            if str(repository.get("id", "")) != repository_id:
                continue
            if repository.get("installed") is True:
                return
        time.sleep(3)
    raise AssertionError(f"HACS repository {repository_id} was not marked as installed in time")


def _hacs_list_integration_repositories(access_token: str) -> list[dict[str, Any]]:
    """Fetch HACS repositories list for integration category."""
    payload = _hacs_ws_command(
        access_token,
        {"type": "hacs/repositories/list", "categories": ["integration"]},
        timeout_seconds=180,
    )
    if not isinstance(payload, list):
        raise AssertionError("Expected list payload from HACS repositories list command")
    return [item for item in payload if isinstance(item, dict)]


def _hacs_ws_command(
    access_token: str,
    command: dict[str, Any],
    *,
    timeout_seconds: int,
) -> Any:
    """Run one HACS websocket command and return `result` payload."""
    return asyncio.run(
        _async_hacs_ws_command(
            access_token=access_token,
            command=command,
            timeout_seconds=timeout_seconds,
        )
    )


async def _async_hacs_ws_command(
    *,
    access_token: str,
    command: dict[str, Any],
    timeout_seconds: int,
) -> Any:
    """Execute websocket command against HA API and parse command result."""
    timeout = aiohttp.ClientTimeout(total=timeout_seconds)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.ws_connect(_HA_WS_URL, heartbeat=30) as websocket:
            initial = await websocket.receive_json(timeout=30)
            if initial.get("type") != "auth_required":
                raise AssertionError(f"Unexpected websocket greeting: {initial}")
            await websocket.send_json({"type": "auth", "access_token": access_token})

            auth = await websocket.receive_json(timeout=30)
            if auth.get("type") != "auth_ok":
                raise AssertionError(f"Websocket auth failed: {auth}")

            request_id = 1
            request_payload = {"id": request_id, **command}
            await websocket.send_json(request_payload)

            deadline = time.time() + timeout_seconds
            while time.time() < deadline:
                message = await websocket.receive_json(timeout=30)
                if message.get("id") != request_id:
                    continue
                if message.get("type") != "result":
                    continue
                if message.get("success") is not True:
                    raise AssertionError(
                        "HACS websocket command failed: "
                        f"{command.get('type')} -> {message.get('error')}"
                    )
                return message.get("result")
    raise AssertionError(f"No websocket result returned for command {command.get('type')}")


def _assert_container_file_exists(container_id: str, path: str) -> None:
    """Assert regular file exists inside Home Assistant container."""
    _run_command(["docker", "exec", container_id, "test", "-f", path])


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


def _auth_headers(access_token: str) -> dict[str, str]:
    """Build common auth headers for HA API calls."""
    return {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }


def _walk_user_case_to_settings_with_wget(
    access_token: str,
    entry_id: str,
) -> None:
    """Go from main UI to integration settings and verify settings availability."""
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

    settings_url = f"{_HA_BASE_URL}/config/integrations/integration/{entry_id}"
    _assert_wget_html_page(settings_url, access_token=access_token)


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
    if method != "GET":
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


