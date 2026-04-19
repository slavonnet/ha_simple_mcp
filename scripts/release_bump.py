"""Update release-related versions for a release PR.

Usage:
    python scripts/release_bump.py 0.1.1

The script updates:
    - ``custom_components/ha_simple_mcp/manifest.json`` -> ``version``
    - dependency pin for ``ha-api-mcp`` git tag (``@vX.Y.Z``) in both:
      - ``pyproject.toml``
      - ``custom_components/ha_simple_mcp/manifest.json``
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")
PYPROJECT_PATH = Path("pyproject.toml")
MANIFEST_PATH = Path("custom_components/ha_simple_mcp/manifest.json")


def _bump_manifest(version: str) -> None:
    """Update manifest version and external package tag pin."""
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    manifest["version"] = version

    requirements = manifest.get("requirements", [])
    updated_requirements: list[str] = []
    for requirement in requirements:
        updated_requirements.append(
            re.sub(
                r"(ha-api-mcp\s*@\s*git\+https://github\.com/slavonnet/ha-api-mcp\.git@)v\d+\.\d+\.\d+",
                rf"\1v{version}",
                requirement,
            )
        )
    manifest["requirements"] = updated_requirements

    MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _bump_pyproject(version: str) -> None:
    """Update pyproject dependency tag pin."""
    content = PYPROJECT_PATH.read_text(encoding="utf-8")
    content = re.sub(
        r"(ha-api-mcp\s*@\s*git\+https://github\.com/slavonnet/ha-api-mcp\.git@)v\d+\.\d+\.\d+",
        rf"\1v{version}",
        content,
    )
    PYPROJECT_PATH.write_text(content, encoding="utf-8")


def main() -> int:
    """Entrypoint for release version bump."""
    if len(sys.argv) != 2:
        print("Usage: python scripts/release_bump.py <x.y.z>")
        return 1

    target_version = sys.argv[1].strip()
    if not SEMVER_RE.fullmatch(target_version):
        print(f"Invalid version format: {target_version}")
        return 1

    _bump_pyproject(target_version)
    _bump_manifest(target_version)
    print(f"Updated release version to {target_version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
