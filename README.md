# QuatroGNC Dashboard

Dashboard Flask para gestión de documentos de vehículos GNC. Herramienta principal: **Procesar Imágenes** (IMG_to_PDF) — convierte fotos de DNI, carnets y documentos en PDFs imprimibles.

## Stack

- **Backend**: Flask 3.0.3, SQLAlchemy ORM, SQLite
- **Frontend**: Jinja2, vanilla JS, vanilla CSS
- **Servidor**: Gunicorn + Nginx (Docker)
- **Seguridad**: Flask-WTF CSRF, rate limiting en login, sesiones filesystem

## Configuracion local

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

flask --app run.py init-db
flask --app run.py seed-db
python run.py
```

App disponible en `http://localhost:5050`.

## Docker (produccion)

Stack de 2 servicios: `web` (Flask + Gunicorn) + `nginx`.

```bash
docker compose up --build
docker compose exec web flask --app run.py init-db
```

## Variables de entorno

| Variable | Descripcion | Default |
|---|---|---|
| `APP_ENV` | `development` / `production` | `development` |
| `SECRET_KEY` | Clave secreta Flask | `dev-secret-change` |
| `DATABASE_URL` | SQLite path | `sqlite:///data/quatro_gnc.db` |
| `SESSION_COOKIE_SECURE` | HTTPS only cookies | `false` |
| `SESSION_COOKIE_SAMESITE` | Cookie SameSite | `Lax` |

## Comandos CLI

```bash
# Inicializar base de datos
flask --app run.py init-db

# Poblar con datos de demo
flask --app run.py seed-db

# Eliminar registros con mas de 20 dias (corre automaticamente a las 23hs ART)
flask --app run.py cleanup-old-jobs
```

## Migracion de datos

Para migrar desde PostgreSQL a SQLite (solo necesario en cutover de servidor):

```bash
# 1. Backup del PostgreSQL origen
./scripts/backup_pg.sh "postgresql+psycopg://user:pass@host/db"

# 2. Migracion selectiva (dry-run primero)
pip install "psycopg[binary]"
python scripts/migrate_pg_to_sqlite.py --pg-url "postgresql+psycopg://..." --dry-run
python scripts/migrate_pg_to_sqlite.py --pg-url "postgresql+psycopg://..."
```

## Auto-delete

Cron configurado en el servidor (02:00 UTC = 23:00 ART) que elimina automaticamente todos los registros con mas de 20 dias, incluyendo los PDFs almacenados.

Log en `/var/log/quatro_gnc_cleanup.log`.

## Seguridad

- Rate limiting en login (in-memory, configurable)
- CSRF en todos los formularios y requests AJAX
- Workspace-scoped: cada usuario solo accede a datos de su workspace
- SSH hardening + UFW + fail2ban en produccion

## Produccion (AWS Lightsail)

- Instancia: 1 vCPU, 1GB RAM + 2GB swap
- OS: Ubuntu 24.04 LTS
- SSL: Cloudflare (modo Flexible)
- Dominio: quatrognc.org
- RAM idle: ~170MB | RAM pico (6 imagenes): ~350-400MB
