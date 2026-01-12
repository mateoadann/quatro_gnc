# Changelog

All notable changes to this project will be documented in this file.

The format is based on "Keep a Changelog" and follows Semantic Versioning.

## [Unreleased]

## [0.1.0] - 2026-01-10
### Added
- Initial SaaS baseline (login local, RPA, IMG_to_PDF, security hardening)
### Changed
- N/A
### Fixed
- N/A

## [1.0.0] - 2026-01-11

### Added
- Autenticación local con Flask‑Login y sesiones server‑side.
- Workspace + roles (admin/user) y branding dinámico por workspace.
- Panel de control para admin: gestión de usuarios, roles, activos y métricas.
- RPA Enargas: creación/consulta por patente, cola RQ, reintentos, descarga/previsualización de PDF.
- Análisis de PDF Enargas para determinar resultado (Renovación / Prueba Hidráulica / Equipo Habilitado).
- IMG_to_PDF: subida múltiple, previsualización, edición (recorte/rotación), generación en background y historial.
- Docker Compose con web/worker/db/redis + Nginx reverse proxy preparado para producción.

### Changed
- UI/UX general: modales, toasts, iconografía y layouts más claros.
- Filtros, orden y paginación en tablas principales.

### Security
- Rate‑limit + bloqueo por intentos fallidos de login.
- Cookies seguras y secretos fuera del repo en producción.