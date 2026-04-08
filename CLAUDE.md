# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Flask dashboard for GNC (gas natural comprimido) vehicle management. Two main tools:
- **IMG_to_PDF**: Processes vehicle images into formatted PDFs
- **RPA_Enargas**: Automated vehicle registration checks via Playwright (headless Chrome) against Enargas website

Multi-tenant workspace model with role-based access (admin/user).

## Tech Stack

- **Backend**: Flask 3.0.3, SQLAlchemy ORM, PostgreSQL 16+, Redis (sessions + queue)
- **Task Queue**: RQ (Redis Queue) with SimpleWorker for background jobs
- **RPA**: Playwright (async, headless Chrome)
- **Frontend**: Jinja2 templates, vanilla JS, vanilla CSS (no framework)
- **Security**: Fernet encryption for credentials, Flask-WTF CSRF, rate-limited login
- **Deployment**: Docker + docker-compose + Nginx reverse proxy

## Commands

```bash
# Local development (requires 3 terminals)
redis-server                          # Terminal 1: Redis
python run.py                         # Terminal 2: Flask dev server (port 5050)
python worker.py                      # Terminal 3: RQ worker

# Database
flask --app run.py init-db            # Create tables
flask --app run.py seed-db            # Seed demo data
flask --app run.py bootstrap-workspace # Update workspace

# Docker
docker compose up --build
docker compose exec web flask --app run.py init-db
docker compose exec web flask --app run.py seed-db

# CI check (no test suite yet)
python -m compileall app              # Syntax validation

# Release
scripts/release.sh X.Y.Z             # Updates CHANGELOG, commits, tags
```

## Architecture

### App Factory Pattern
- `app/__init__.py` — factory function, registers blueprints, CLI commands
- `app/extensions.py` — SQLAlchemy, Flask-Login, CSRF, Session initialization
- `app/config.py` — env-based config (development/production differences)

### Request Flow
Routes (`app/routes.py`) act as controllers. Business logic lives in `app/services/`. Background work goes through RQ tasks (`app/tasks.py`).

### Key Patterns
- **Workspace-scoped queries**: All data queries filter by `current_user.workspace_id`
- **Deferred binary columns**: `pdf_data` uses `deferred()` to avoid loading large blobs
- **AJAX partials**: Tables refresh via AJAX returning HTML fragments from `templates/partials/`
- **Stale process cleanup**: `_mark_stale_processes()` marks "en proceso" as "error" after `RPA_STALE_MINUTES` (default 15)
- **Encrypted credentials**: Enargas passwords encrypted with Fernet via `app/utils.py`
- **RPA session management**: `app/services/rpa_session.py` manages a singleton Playwright browser session with thread-safe locks

### Services
- `app/services/rpa_enargas.py` — Playwright automation against Enargas website
- `app/services/process_pdf_enargas.py` — PDF field extraction from Enargas results
- `app/services/img_to_pdf.py` — Image processing and PDF generation
- `app/services/img_pdf/` — Document processing library (OpenCV, Pillow, NumPy)

### Models
- `User` — local auth, role (admin/user), workspace-scoped
- `Workspace` — tenant isolation
- `EnargasCredentials` — encrypted third-party login
- `Proceso` — RPA execution records (patente, estado, resultado, pdf_data)
- `Taller` — mechanic workshops linked to procesos
- `ImgToPdfJob` — image-to-PDF job tracking

## Git Workflow

- **Branches**: `feature/<topic>`, `fix/<topic>`, `chore/<topic>`, `hotfix/<topic>`
- **Flow**: branch from develop/main → PR → merge → tag release
- **Versioning**: SemVer. CHANGELOG.md uses `[Unreleased]` section during development
- **CI**: `.github/workflows/ci.yml` runs `python -m compileall app`

## Configuration

Key env vars (see `.env.example` for full list):
- `APP_ENV` — development/production (affects session type, cookie security)
- `DATABASE_URL` — PostgreSQL connection string
- `REDIS_URL` — Redis for sessions and RQ
- `ENCRYPTION_KEY` — Fernet key for credential encryption
- `RPA_HEADLESS` — Playwright headless mode (default true)
- `RPA_STALE_MINUTES` — Timeout for stuck processes (default 15)
- `RPA_PER_PAGE` — Pagination size (default 10)

## Conventions

- All UI text is in Spanish
- Login has rate limiting and account lockout (Redis-backed)
- No CORS (internal tool, not a public API)
- Production uses Gunicorn (`wsgi.py`) behind Nginx
- Feature flags strategy documented in `docs/feature_flags.md` (not yet implemented)
