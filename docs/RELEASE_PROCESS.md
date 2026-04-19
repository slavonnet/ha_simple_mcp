# Release process

This repository uses a **release-via-PR** workflow.

## Goals

- Avoid missing updates when upstream `ha-api-mcp` gets a new release.
- Keep versions synchronized across files and tags.
- Enforce dependency vulnerability audit in CI.
- Publish HACS from versioned releases (not from default branch).

## Branch and PR model

1. Create release branch:

   ```bash
   git checkout -b release/X.Y.Z
   ```

2. Bump versions using helper script:

   ```bash
   python3 scripts/release_bump.py X.Y.Z
   ```

   This updates:
   - `custom_components/ha_simple_mcp/manifest.json` -> `version`

   Note: package version in `pyproject.toml` is now dynamic (from git tags via
   `setuptools_scm`), so no manual bump is required there.
   Note: version of external `ha-api-mcp` dependency is independent and is not
   auto-aligned to release branch version of this repository.

3. Open PR from `release/X.Y.Z` to `main`.

   `Release PR Check` now auto-runs `scripts/release_bump.py X.Y.Z` in the
   release branch and pushes synchronized `manifest.json` version back into the
   PR when drift is detected.

4. CI checks:
   - `CI` workflow (lint, mypy, tests, 100% coverage)
   - `Security Audit` workflow (`pip-audit --strict`)
   - `Release PR Check` workflow (ensures release branch name and manifest are aligned)

   Note: dependency audit runs in an isolated clean environment against the
   project dependency graph, including externally pinned `ha-api-mcp`.

5. Merge PR.

6. Create tag and release:

   ```bash
   git checkout main
   git pull origin main
   git tag vX.Y.Z
   git push origin vX.Y.Z
   ```

   Tag push triggers `Release` workflow:
   - validates that tag matches `manifest.json` version
   - builds `dist/ha_simple_mcp.zip` artifact for HACS release
   - publishes `ha_simple_mcp.zip` as GitHub Release asset

7. If release asset is missing, re-run publication manually:

   - Go to **Actions -> Release -> Run workflow**
   - Pass an existing tag in input `tag` (for example `v0.1.1` or `0.1.1`)
   - Workflow first normalizes and validates the tag format (`vX.Y.Z` or `X.Y.Z`)
   - Workflow then checks that the tag exists on remote and fails with
     an explicit message if tag is missing
   - Workflow then aligns release metadata in-place (`manifest.json`) using
     `scripts/release_bump.py`
   - Finally it re-publishes `ha_simple_mcp.zip` into the selected release

## HACS versioned mode

`hacs.json` is configured to use release artifacts:

- `"zip_release": true`
- `"filename": "ha_simple_mcp.zip"`
- `"hide_default_branch": true`

This forces consumption of explicit versions/releases rather than the default branch.
