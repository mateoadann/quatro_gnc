# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Flask dashboard for GNC (gas natural comprimido) vehicle management. One tool:
- **IMG_to_PDF**: Processes photos of documents (DNI, carnets) into a printable single-page PDF

Multi-tenant workspace model with role-based access (admin/user).

## Tech Stack

- **Backend**: Flask 3.0.3, SQLAlchemy ORM; PostgreSQL on Neon in production, SQLite locally
- **Frontend**: Jinja2 templates, vanilla JS, vanilla CSS (no framework)
- **Security**: Flask-WTF CSRF, DB-backed login rate limiting, signed cookie sessions
- **Deployment**: Vercel (Python 3.12, Fluid Compute, region `gru1`), Vercel Cron

## Commands

```bash
# Local development
python run.py                         # Flask dev server (port 5050)

# Database
flask --app run.py init-db            # Create tables
flask --app run.py seed-db            # Seed demo data
flask --app run.py bootstrap-workspace # Update workspace

# Deploy (personal Vercel account)
vercel -Q ~/.vercel-personal --scope mateo-adans-projects --prod

# CI check (no test suite yet)
python -m compileall app              # Syntax validation

# Release
scripts/release.sh X.Y.Z             # Updates CHANGELOG, commits, tags
```

## Architecture

### App Factory Pattern
- `app/__init__.py` — factory function, registers blueprints, CLI commands
- `app/extensions.py` — SQLAlchemy, Flask-Login, CSRF
- `app/config.py` — env-based config (development/production differences)

### Request Flow
Routes (`app/routes.py`) act as controllers. Business logic lives in `app/services/`. Everything runs inside the request; there is no background worker.

### Key Patterns
- **Workspace-scoped queries**: All data queries filter by `current_user.workspace_id`
- **Deferred binary columns**: `pdf_data` uses `deferred()` to avoid loading large blobs
- **AJAX partials**: Tables refresh via AJAX returning HTML fragments from `templates/partials/`
- **4.5 MB request limit**: Vercel rejects bigger bodies, so `main.js` downscales photos client-side before upload
- **Job cleanup**: Vercel Cron hits `/cron/cleanup-jobs` daily (checks `CRON_SECRET`) and deletes jobs older than 20 days

### Services
- `app/services/img_to_pdf.py` — Image processing and PDF generation
- `app/services/img_pdf/` — Document processing library (OpenCV, Pillow, NumPy)

### Models
- `User` — local auth, role (admin/user), workspace-scoped
- `Workspace` — tenant isolation
- `ImgToPdfJob` — image-to-PDF job tracking
- `LoginThrottle` — login rate-limit and lockout counters

## Git Workflow

- **Branches**: `feature/<topic>`, `fix/<topic>`, `chore/<topic>`, `hotfix/<topic>`
- **Flow**: branch from develop/main → PR → merge → tag release
- **Versioning**: SemVer. CHANGELOG.md uses `[Unreleased]` section during development
- **CI**: `.github/workflows/ci.yml` runs `python -m compileall app`

## Configuration

Key env vars (see `.env.example` for full list):
- `APP_ENV` — development/production (affects cookie security)
- `DATABASE_URL` — Neon Postgres or SQLite
- `SECRET_KEY` — signs the session cookie
- `CRON_SECRET` — bearer token Vercel Cron sends to `/cron/cleanup-jobs`

## Conventions

- All UI text is in Spanish
- Login has rate limiting and account lockout (DB-backed, `login_throttle` table)
- No CORS (internal tool, not a public API)
- Feature flags strategy documented in `docs/feature_flags.md` (not yet implemented)
