# QuatroGNC Dashboard

Primeros pasos para un dashboard Flask con dos herramientas: IMG_to_PDF y RPA_Enargas.

## Features incluidas
- Login/logout con usuarios locales (Flask-Login).
- Layout responsivo con navbar para alternar herramientas.
- Seccion de usuario para editar credenciales Enargas.
- Conexion a Postgres con SQLAlchemy y tablas iniciales.
- Dockerfile y docker-compose para despliegue rapido.

## Requisitos
- Python 3.11+ (compatible con 3.13 via psycopg3)
- Postgres 16+ (o Docker)
- Playwright (para RPA_Enargas)
- Redis (para cola RQ)

## Configuracion local
1) Crear entorno virtual e instalar dependencias:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Si vas a usar RPA_Enargas, instala el navegador:

```bash
playwright install chromium
```

Si vas a usar el procesamiento en background:

```bash
redis-server
```

2) Crear un `.env` desde el ejemplo (usa `postgresql+psycopg://`):

```bash
cp .env.example .env
```

3) Inicializar y poblar la base:

```bash
flask --app run.py init-db
flask --app run.py seed-db
```

4) Ejecutar:

```bash
python run.py
```

En otra terminal, iniciar el worker RQ:

```bash
python worker.py
```

Login:
- Usar el usuario local creado con `seed-db` o uno cargado en la base.

## Seguridad (produccion)
- Setear `APP_ENV=production`.
- Usar valores reales para `SECRET_KEY` y `ENCRYPTION_KEY`.
- `SESSION_COOKIE_SECURE=true` y `SESSION_TYPE=redis`.
- `ALLOW_SEED_DEMO=false` para evitar usuarios/demo.
- Rate limit y bloqueo por intentos fallidos en login:
  - `LOGIN_RATE_LIMIT`, `LOGIN_RATE_WINDOW`
  - `LOGIN_FAIL_LIMIT`, `LOGIN_LOCKOUT_SECONDS`

## Docker

```bash
docker compose up --build
```

Luego inicializa la base con:

```bash
docker compose exec web flask --app run.py init-db
docker compose exec web flask --app run.py seed-db
```

Si queres levantar solo algunos servicios:

```bash
docker compose up --build web db redis
```

## Reverse proxy con Nginx (pre-produccion)

Incluye un contenedor `nginx` que expone el puerto 80 y reenvia al servicio `web`.

1) Configura variables seguras en tu `.env` (no en el repo):
```bash
APP_ENV=production
SECRET_KEY=...
ENCRYPTION_KEY=...
SESSION_TYPE=redis
SESSION_COOKIE_SECURE=true
```

2) Levanta los servicios:
```bash
docker compose up --build
```

3) Cuando tengas el dominio y el certificado HTTPS, agrega los certificados
en `./nginx/certs` y configura el bloque `server` en Nginx para el puerto 443.

## Integracion de herramientas
El codigo de ambas herramientas debe integrarse en:
- `app/services/img_to_pdf.py`
- `app/services/rpa_enargas.py`

Luego se puede conectar la logica a nuevos endpoints en `app/routes.py`.

## Usuarios locales
- Los usuarios se guardan en la base local con password hash.
- En desarrollo podes crear uno con `seed-db` o insertarlo manualmente.
