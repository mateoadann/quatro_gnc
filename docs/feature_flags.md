# Feature Flags (SaaS Strategy)

Goal: keep one codebase while enabling/disabling features per client.

## Recommended approach
Use a simple, predictable hierarchy:

1) Defaults in code (safe values)
2) Environment overrides (global per deployment)
3) Database overrides (per client)

This keeps local/dev simple and lets you customize per client later.

## Minimal flag catalog (example)
Pick flags that match real product switches:

- `FEATURE_RPA_ENABLED`
- `FEATURE_IMG_TO_PDF_ENABLED`
- `FEATURE_PDF_ANALYSIS_ENABLED`
- `FEATURE_RPA_RETRY_ENABLED`
- `FEATURE_ADVANCED_EDIT_ENABLED`

## Data model (for multi-client)
Add two tables when you are ready for multi-client:

- `tenant`: id, name, slug, created_at
- `tenant_flag`: tenant_id, flag_key, enabled, value_json, updated_at

Rules:
- If a `tenant_flag` exists, it overrides env and defaults.
- If it does not exist, fall back to env or default.

## Where to read flags
Centralize flag evaluation in one place (helper function).
Example behavior:

- `get_flag("FEATURE_RPA_ENABLED", tenant_id)` -> True/False
- Reads DB first, then env, then default

This keeps templates, routes, and tasks consistent.

## How to apply flags
Examples:

- Hide tools in the navbar if a flag is off.
- Disable routes or return 404/403 for disabled tools.
- Skip RQ jobs if a feature is disabled.

## Operational workflow
1) New feature behind a flag (default off).
2) Test in staging (enable flag).
3) Enable for one client in production.
4) If stable, enable by default and remove the flag later.

## Guard rails
- Keep flags typed (bool or json).
- Log which flags are active for each request (debug only).
- Remove stale flags to avoid permanent clutter.

