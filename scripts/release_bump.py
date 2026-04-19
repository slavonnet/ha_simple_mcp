"""Update integration release version for a release PR.

Usage:
    python scripts/release_bump.py 0.1.1

The script updates:
    - ``custom_components/ha_simple_mcp/manifest.json`` -> ``version``
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import re

SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")
MANIFEST_PATH = Path("custom_components/ha_simple_mcp/manifest.json")


def _bump_manifest(version: str) -> None:
    """Update integration version in manifest."""
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    manifest["version"] = version

    MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    """Entrypoint for release version bump."""
    if len(sys.argv) != 2:
        print("Usage: python scripts/release_bump.py <x.y.z>")
        return 1

    target_version = sys.argv[1].strip()
    if not SEMVER_RE.fullmatch(target_version):
        print(f"Invalid version format: {target_version}")
        return 1

    _bump_manifest(target_version)
    print(f"Updated release version to {target_version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
