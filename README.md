# QuatroGNC Dashboard

Primeros pasos para un dashboard Flask con dos herramientas: IMG_to_PDF y RPA_Enargas.

## Features incluidas
- Login/logout (local) y placeholders para Keycloak.
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

Login inicial (configurable via env):
- Usuario: `admin`
- Contrasena: `admin123`

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
Se dejaron variables de entorno en `.env.example` y un endpoint placeholder en `/login/keycloak`.
Para integracion real, agregar el flujo OAuth/OpenID Connect y validar los tokens.
