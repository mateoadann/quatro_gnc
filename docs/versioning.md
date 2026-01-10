# Versioning and Releases

This project uses Semantic Versioning (SemVer):

- MAJOR: breaking changes (backward incompatible)
- MINOR: new features (backward compatible)
- PATCH: bug fixes only

## Files involved
- `CHANGELOG.md`: human readable log of changes.
- `scripts/release.sh`: updates the changelog, creates a commit, and tags a release.

## How to use the changelog
Keep changes under `## [Unreleased]` while you develop.
Use sections to keep it clear:

- Added: new features
- Changed: behavior changes
- Fixed: bug fixes
- Removed: deprecations (optional)

Example:

```
## [Unreleased]
### Added
- New PDF analysis result "Equipo Habilitado"
### Fixed
- RPA error details now open in a modal
```

## Releasing a new version
1) Make sure the working tree is clean:
```
git status
```

2) Run the release script with a SemVer number:
```
scripts/release.sh 1.4.0
```

This will:
- move `[Unreleased]` into `## [1.4.0] - YYYY-MM-DD`
- create a commit "Release v1.4.0"
- create a git tag `v1.4.0`

3) Push:
```
git push
git push --tags
```

## Picking the correct version
Use this rule of thumb:

- PATCH (1.4.1): UI fixes, small bug fixes, no behavior change
- MINOR (1.5.0): new feature flag, new tool, new table, new endpoint
- MAJOR (2.0.0): breaking change (data model, auth flow, API changes)

## SaaS client updates (single repo)
For multiple clients with the same codebase:

- Keep one repo and deploy the same version everywhere.
- Use per-client env vars or feature flags to enable/disable features.
- If a client needs a custom flow, use a feature flag and keep the code unified.

Suggested practice:
- Store the deployed version in a variable, e.g. `APP_VERSION=1.4.0`.
- Log it in the UI footer or admin settings for support.

