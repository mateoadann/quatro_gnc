# GitHub workflow

## Branching
- main: production only. All changes enter via PR.
- develop: integration branch (optional for small teams).
- feature/<topic>: new features.
- fix/<topic>: bug fixes.
- chore/<topic>: maintenance, docs, refactors.
- hotfix/<topic>: urgent fixes to production.

Suggested flow:
1) Create branch from develop (or main if you skip develop).
2) Open PR into develop.
3) Merge develop into main for release.
4) Tag the release (vX.Y.Z).

## Protection rules (GitHub settings)
Apply to `main` (and `develop` if used):
- Require pull request reviews (>= 1 approval).
- Require status checks to pass (CI).
- Require linear history (optional but recommended).
- Restrict who can push to the branch (no direct pushes).
- Do not allow force pushes.

## CI (minimal)
File: `.github/workflows/ci.yml`
- Install Python dependencies.
- Run `python -m compileall app` to catch syntax errors.

## Releases
- Tag release: `vX.Y.Z`
- Create a GitHub Release with a short changelog.

