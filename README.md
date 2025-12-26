# QuatroGNC Dashboard

Primeros pasos para un dashboard Flask con dos herramientas: IMG_to_PDF y RPA_Enargas.

## Features incluidas
- Login/logout con Keycloak (OIDC).
- Layout responsivo con navbar para alternar herramientas.
- Seccion de usuario para editar credenciales Enargas.
- Conexion a Postgres con SQLAlchemy y tablas iniciales.
- Dockerfile y docker-compose para despliegue rapido.

## Requisitos
- Python 3.11+ (compatible con 3.13 via psycopg3)
- Postgres 16+ (o Docker)

## Configuracion local
1) Crear entorno virtual e instalar dependencias:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
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

Login con Keycloak:
- Usar un usuario creado en el realm configurado.

## Docker

```bash
docker compose up --build
```

Luego inicializa la base con:

```bash
docker compose exec web flask --app run.py init-db
docker compose exec web flask --app run.py seed-db
```

## Integracion de herramientas
El codigo de ambas herramientas debe integrarse en:
- `app/services/img_to_pdf.py`
- `app/services/rpa_enargas.py`

Luego se puede conectar la logica a nuevos endpoints en `app/routes.py`.

## Keycloak
Se dejaron variables de entorno en `.env.example` para integrar el flujo OIDC.
La app usa el formulario propio y valida contra Keycloak con **Direct Access Grants**.

Pasos recomendados:
1) En Keycloak, crear un cliente "Confidential" con:
   - Direct Access Grants: **ON**
   - Redirect URI: `http://localhost:5000/auth/keycloak/callback` (opcional si luego queres SSO)
   - Post logout redirect URI: `http://localhost:5000/login`
2) En `.env`, configurar:
   - `KEYCLOAK_ENABLED=true`
   - `KEYCLOAK_BASE_URL`, `KEYCLOAK_REALM`, `KEYCLOAK_CLIENT_ID`, `KEYCLOAK_CLIENT_SECRET`
   - `KEYCLOAK_REDIRECT_URI` y `KEYCLOAK_POST_LOGOUT_REDIRECT_URI` si son distintos

La app crea usuarios locales si `KEYCLOAK_AUTO_PROVISION=true`.
