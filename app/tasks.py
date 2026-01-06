from . import create_app
from .extensions import db
from .models import EnargasCredentials, Proceso
import traceback

from .services.rpa_enargas import NoOperacionesError, SessionActivaError, run_rpa


def process_rpa_job(proceso_id: int) -> None:
    app = create_app()
    with app.app_context():
        proceso = Proceso.query.get(proceso_id)
        if not proceso:
            return

        credentials = EnargasCredentials.query.filter_by(user_id=proceso.user_id).first()
        if not credentials:
            proceso.estado = "error"
            proceso.resultado = None
            proceso.pdf_data = None
            proceso.pdf_filename = None
            proceso.error_message = "Credenciales de Enargas no configuradas."
            db.session.commit()
            return

        enargas_password = credentials.get_password()
        if not enargas_password:
            proceso.estado = "error"
            proceso.resultado = None
            proceso.pdf_data = None
            proceso.pdf_filename = None
            proceso.error_message = "Contrasena de Enargas no configurada."
            db.session.commit()
            return

        try:
            result = run_rpa(proceso.patente, credentials.enargas_user, enargas_password)
            proceso.estado = "completado"
            proceso.resultado = result.get("resultado") or "Renovación de Oblea"
            proceso.pdf_data = result.get("pdf_data")
            proceso.pdf_filename = result.get("pdf_filename")
            proceso.error_message = None
        except NoOperacionesError:
            proceso.estado = "completado"
            proceso.resultado = "Patente NO registrada"
            proceso.pdf_data = None
            proceso.pdf_filename = None
            proceso.error_message = None
        except SessionActivaError:
            proceso.estado = "completado"
            proceso.resultado = "Sesión Activa"
            proceso.pdf_data = None
            proceso.pdf_filename = None
            proceso.error_message = "Reintentar"
        except Exception:
            proceso.estado = "error"
            proceso.resultado = None
            proceso.pdf_data = None
            proceso.pdf_filename = None
            proceso.error_message = _format_error()

        db.session.commit()


def _format_error() -> str:
    detail = traceback.format_exc()
    if not detail:
        return "Error desconocido en el proceso RPA."
    return detail[-1200:]
