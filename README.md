# QuatroGNC Dashboard

Dashboard Flask para gestión de documentos de vehículos GNC. Herramienta principal: **Procesar Imágenes** (IMG_to_PDF) — convierte fotos de DNI, carnets y documentos en PDFs imprimibles.

## Stack

- **Backend**: Flask 3.0.3, SQLAlchemy ORM, PostgreSQL (Neon) en producción, SQLite en local
- **Frontend**: Jinja2, vanilla JS, vanilla CSS
- **Hosting**: Vercel (Python 3.12, Fluid Compute, región `gru1`)
- **Seguridad**: Flask-WTF CSRF, rate limiting en login (en la DB), sesiones en cookie firmada

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

App disponible en `http://localhost:5050`. Sin `DATABASE_URL` usa SQLite en `data/quatro_gnc.db`.

## Deploy

Proyecto Vercel `mateo-adans-projects/quatro-gnc`, con la base Neon conectada por la integración del Marketplace.

```bash
vercel --prod
```

Las tablas se crean con `flask --app run.py init-db` apuntando `DATABASE_URL` a Neon (`vercel env pull`).

## Variables de entorno

| Variable | Descripcion | Default |
|---|---|---|
| `APP_ENV` | `development` / `production` | `development` |
| `SECRET_KEY` | Clave secreta Flask (firma la cookie de sesión) | `dev-secret-change` |
| `DATABASE_URL` | Postgres (Neon) o SQLite | `sqlite:///data/quatro_gnc.db` |
| `CRON_SECRET` | Token que Vercel Cron manda a `/cron/cleanup-jobs` | vacío (ruta deshabilitada) |
| `SESSION_COOKIE_SECURE` | HTTPS only cookies | `false` |
| `SESSION_COOKIE_SAMESITE` | Cookie SameSite | `Lax` |

## Comandos CLI

```bash
# Inicializar base de datos
flask --app run.py init-db

# Poblar con datos de demo
flask --app run.py seed-db
```

## Auto-delete

Vercel Cron (`vercel.json`, 02:00 UTC = 23:00 ART) llama a `/cron/cleanup-jobs`, que elimina los registros con más de 20 días, incluyendo los PDFs almacenados.

## Limites

- Vercel rechaza requests de más de 4.5 MB: el navegador achica las fotos (máx. 1800px, JPEG) antes de subirlas.

## Seguridad

- Rate limiting por IP y bloqueo por usuario en login (tabla `login_throttle`, configurable)
- CSRF en todos los formularios y requests AJAX
- Workspace-scoped: cada usuario solo accede a datos de su workspace

## Produccion

- URL: https://quatrognc.org (DNS en Cloudflare, sin proxy, apuntando a Vercel)
