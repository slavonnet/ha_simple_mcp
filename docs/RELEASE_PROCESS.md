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
   - `pyproject.toml` -> `project.version`
   - `custom_components/ha_simple_mcp/manifest.json` -> `version`
   - pin of external dependency `ha-api-mcp` tag to `vX.Y.Z`

3. Open PR from `release/X.Y.Z` to `main`.

4. CI checks:
   - `CI` workflow (lint, mypy, tests, 100% coverage)
   - `Security Audit` workflow (`pip-audit --strict`)
   - `Release PR Check` workflow (ensures branch name and versions are aligned)

5. Merge PR.

6. Create tag and release:

   ```bash
   git checkout main
   git pull origin main
   git tag vX.Y.Z
   git push origin vX.Y.Z
   ```

   Tag push triggers `Release` workflow:
   - validates that tag matches versions in files
   - builds `dist/ha_simple_mcp.zip` artifact for HACS release

## HACS versioned mode

`hacs.json` is configured to use release artifacts:

- `"zip_release": true`
- `"filename": "ha_simple_mcp.zip"`
- `"hide_default_branch": true`

This forces consumption of explicit versions/releases rather than the default branch.
