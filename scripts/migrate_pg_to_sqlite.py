#!/usr/bin/env python3
"""
Migrate Users, Workspaces, and ImgToPdfJobs from PostgreSQL to SQLite.

Run once during the Hostinger -> Lightsail cutover.

Requirements (install temporarily, not in requirements.txt):
    pip install "psycopg[binary]"
    # or alternatively:
    pip install psycopg2-binary

Usage:
    python scripts/migrate_pg_to_sqlite.py \
        --pg-url "postgresql+psycopg://user:pass@host:5432/dbname" \
        --sqlite-path data/quatro_gnc.db

    # Dry run (show counts, don't write):
    python scripts/migrate_pg_to_sqlite.py \
        --pg-url "postgresql+psycopg://user:pass@host:5432/dbname" \
        --dry-run

    # Skip ImgToPdfJob (avoids large BLOBs):
    python scripts/migrate_pg_to_sqlite.py \
        --pg-url "postgresql+psycopg://user:pass@host:5432/dbname" \
        --skip-jobs
"""

import argparse
import os
import sys

# ---------------------------------------------------------------------------
# Driver availability check
# ---------------------------------------------------------------------------

def _check_pg_driver(pg_url: str) -> None:
    """Verify that the required PostgreSQL driver is importable."""
    if "psycopg2" in pg_url or "+psycopg2" in pg_url:
        driver = "psycopg2"
    else:
        driver = "psycopg"

    try:
        __import__(driver)
    except ImportError:
        print(f"\nERROR: PostgreSQL driver '{driver}' is not installed.")
        print("Install it temporarily with one of:")
        print('    pip install "psycopg[binary]"')
        print("    pip install psycopg2-binary")
        print("\nThen re-run this script.\n")
        sys.exit(1)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

JOB_BATCH_SIZE = 10


def _count_rows(engine, table_name: str) -> int:
    from sqlalchemy import text

    with engine.connect() as conn:
        result = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}"))  # noqa: S608
        return result.scalar()


def _table_has_rows(engine, table_name: str) -> bool:
    try:
        return _count_rows(engine, table_name) > 0
    except Exception:
        return False


def _print_counts(label: str, engine, tables: list[str]) -> None:
    print(f"\n  {label}:")
    for t in tables:
        try:
            print(f"    {t}: {_count_rows(engine, t)}")
        except Exception:
            print(f"    {t}: (table not found)")


# ---------------------------------------------------------------------------
# Migration logic
# ---------------------------------------------------------------------------

def migrate(
    pg_url: str,
    sqlite_path: str,
    skip_jobs: bool,
    dry_run: bool,
) -> None:
    from sqlalchemy import create_engine, text

    # ---- source (PostgreSQL) ----
    _check_pg_driver(pg_url)
    pg_engine = create_engine(pg_url)

    tables = ["workspace", "user"]
    if not skip_jobs:
        tables.append("img_to_pdf_job")

    # Show source counts
    print("--- Source (PostgreSQL) ---")
    _print_counts("Row counts", pg_engine, tables)

    if dry_run:
        print("\n[DRY RUN] No changes were made.\n")
        pg_engine.dispose()
        return

    # ---- target (SQLite via Flask app) ----
    # We override DATABASE_URL so the Flask app points to the target SQLite.
    abs_sqlite = os.path.abspath(sqlite_path)
    os.environ["DATABASE_URL"] = f"sqlite:///{abs_sqlite}"

    # Ensure parent directory exists
    os.makedirs(os.path.dirname(abs_sqlite) or ".", exist_ok=True)

    # Import app AFTER setting DATABASE_URL so it picks up the SQLite path.
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    from app import create_app
    from app.extensions import db

    app = create_app()

    with app.app_context():
        sqlite_engine = db.engine

        # Safety: check if target already has data
        db.create_all()
        if _table_has_rows(sqlite_engine, "workspace"):
            answer = input(
                "\nWARNING: Target SQLite database already contains data.\n"
                "Do you want to DELETE existing data and overwrite? (yes/no): "
            )
            if answer.strip().lower() not in ("yes", "y"):
                print("Aborted.")
                pg_engine.dispose()
                return

            # Truncate in reverse FK order
            for t in reversed(tables):
                db.session.execute(text(f"DELETE FROM {t}"))
            db.session.commit()

        # ---- copy workspace ----
        print("\nMigrating workspace ...")
        with pg_engine.connect() as pg_conn:
            rows = pg_conn.execute(
                text("SELECT id, name, created_at FROM workspace ORDER BY id")
            ).fetchall()

        for row in rows:
            db.session.execute(
                text(
                    "INSERT INTO workspace (id, name, created_at) "
                    "VALUES (:id, :name, :created_at)"
                ),
                {"id": row.id, "name": row.name, "created_at": row.created_at},
            )
        db.session.commit()
        print(f"  -> {len(rows)} workspaces copied.")

        # ---- copy user ----
        print("Migrating user ...")
        with pg_engine.connect() as pg_conn:
            rows = pg_conn.execute(
                text(
                    "SELECT id, workspace_id, username, password_hash, "
                    "first_name, last_name, role, is_active, created_at "
                    "FROM \"user\" ORDER BY id"
                )
            ).fetchall()

        for row in rows:
            db.session.execute(
                text(
                    "INSERT INTO user "
                    "(id, workspace_id, username, password_hash, "
                    "first_name, last_name, role, is_active, created_at) "
                    "VALUES (:id, :workspace_id, :username, :password_hash, "
                    ":first_name, :last_name, :role, :is_active, :created_at)"
                ),
                {
                    "id": row.id,
                    "workspace_id": row.workspace_id,
                    "username": row.username,
                    "password_hash": row.password_hash,
                    "first_name": row.first_name,
                    "last_name": row.last_name,
                    "role": row.role,
                    "is_active": row.is_active,
                    "created_at": row.created_at,
                },
            )
        db.session.commit()
        print(f"  -> {len(rows)} users copied.")

        # ---- copy img_to_pdf_job (batched) ----
        if not skip_jobs:
            print("Migrating img_to_pdf_job (batched) ...")
            with pg_engine.connect() as pg_conn:
                total = pg_conn.execute(
                    text("SELECT COUNT(*) FROM img_to_pdf_job")
                ).scalar()

            copied = 0
            offset = 0

            while offset < total:
                with pg_engine.connect() as pg_conn:
                    rows = pg_conn.execute(
                        text(
                            "SELECT id, user_id, workspace_id, created_by_user_id, "
                            "filename, page_count, status, pdf_filename, pdf_data, "
                            "error_message, created_at, updated_at "
                            "FROM img_to_pdf_job ORDER BY id "
                            "LIMIT :limit OFFSET :offset"
                        ),
                        {"limit": JOB_BATCH_SIZE, "offset": offset},
                    ).fetchall()

                for row in rows:
                    db.session.execute(
                        text(
                            "INSERT INTO img_to_pdf_job "
                            "(id, user_id, workspace_id, created_by_user_id, "
                            "filename, page_count, status, pdf_filename, pdf_data, "
                            "error_message, created_at, updated_at) "
                            "VALUES (:id, :user_id, :workspace_id, :created_by_user_id, "
                            ":filename, :page_count, :status, :pdf_filename, :pdf_data, "
                            ":error_message, :created_at, :updated_at)"
                        ),
                        {
                            "id": row.id,
                            "user_id": row.user_id,
                            "workspace_id": row.workspace_id,
                            "created_by_user_id": row.created_by_user_id,
                            "filename": row.filename,
                            "page_count": row.page_count,
                            "status": row.status,
                            "pdf_filename": row.pdf_filename,
                            "pdf_data": row.pdf_data,
                            "error_message": row.error_message,
                            "created_at": row.created_at,
                            "updated_at": row.updated_at,
                        },
                    )
                db.session.commit()
                copied += len(rows)
                offset += JOB_BATCH_SIZE
                print(f"    batch {offset // JOB_BATCH_SIZE}: {copied}/{total} jobs")

            print(f"  -> {copied} jobs copied.")

        # ---- verification ----
        print("\n--- Verification ---")
        _print_counts("Destination (SQLite)", sqlite_engine, tables)

        # FK integrity
        print("\n  Foreign key checks:")
        orphan_users = db.session.execute(
            text(
                "SELECT COUNT(*) FROM user u "
                "WHERE u.workspace_id IS NOT NULL "
                "AND u.workspace_id NOT IN (SELECT id FROM workspace)"
            )
        ).scalar()
        print(f"    Users with invalid workspace_id: {orphan_users}")

        if not skip_jobs:
            orphan_jobs_user = db.session.execute(
                text(
                    "SELECT COUNT(*) FROM img_to_pdf_job j "
                    "WHERE j.user_id NOT IN (SELECT id FROM user)"
                )
            ).scalar()
            orphan_jobs_ws = db.session.execute(
                text(
                    "SELECT COUNT(*) FROM img_to_pdf_job j "
                    "WHERE j.workspace_id IS NOT NULL "
                    "AND j.workspace_id NOT IN (SELECT id FROM workspace)"
                )
            ).scalar()
            print(f"    Jobs with invalid user_id: {orphan_jobs_user}")
            print(f"    Jobs with invalid workspace_id: {orphan_jobs_ws}")

        # Password hash sanity
        empty_hashes = db.session.execute(
            text(
                "SELECT COUNT(*) FROM user "
                "WHERE password_hash IS NULL OR LENGTH(password_hash) = 0"
            )
        ).scalar()
        print(f"\n  Users with empty/null password_hash: {empty_hashes}")

        if orphan_users == 0 and empty_hashes == 0:
            print("\n  All checks passed.")
        else:
            print("\n  WARNING: Some checks failed. Review the data above.")

    pg_engine.dispose()
    print("\nMigration complete.\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migrate data from PostgreSQL to SQLite (one-time cutover)."
    )
    parser.add_argument(
        "--pg-url",
        required=True,
        help=(
            "PostgreSQL connection string, e.g. "
            '"postgresql+psycopg://user:pass@host:5432/dbname"'
        ),
    )
    parser.add_argument(
        "--sqlite-path",
        default="data/quatro_gnc.db",
        help="Path to target SQLite file (default: data/quatro_gnc.db)",
    )
    parser.add_argument(
        "--skip-jobs",
        action="store_true",
        help="Skip ImgToPdfJob migration (avoids large BLOBs)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be migrated without writing anything",
    )
    args = parser.parse_args()

    migrate(
        pg_url=args.pg_url,
        sqlite_path=args.sqlite_path,
        skip_jobs=args.skip_jobs,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
