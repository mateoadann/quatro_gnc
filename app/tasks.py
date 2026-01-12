from . import create_app
from .extensions import db
from .models import EnargasCredentials, ImgToPdfJob, Proceso
from .queue import get_queue
import traceback
from pathlib import Path
import shutil

from .services.rpa_enargas import NoOperacionesError, SessionActivaError, run_rpa
from .services.process_pdf_enargas import analyze_pdf_bytes
from .services.img_to_pdf import create_pdf_from_files


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
            proceso.resultado = None
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
        except Exception as exc:
            message = str(exc or "").lower()
            if "credenciales invalidas" in message:
                proceso.estado = "completado"
                proceso.resultado = "Credenciales inválidas"
                proceso.pdf_data = None
                proceso.pdf_filename = None
                proceso.error_message = (
                    "Credenciales de Enargas inválidas. "
                    "Revisa Usuario > Credenciales."
                )
            else:
                proceso.estado = "error"
                proceso.resultado = None
                proceso.pdf_data = None
                proceso.pdf_filename = None
                proceso.error_message = _format_error()

        db.session.commit()

        if proceso.estado == "completado" and proceso.pdf_data:
            queue = get_queue()
            queue.enqueue("app.tasks.process_pdf_job", proceso.id)


def process_pdf_job(proceso_id: int) -> None:
    app = create_app()
    with app.app_context():
        proceso = Proceso.query.get(proceso_id)
        if not proceso or not proceso.pdf_data:
            return

        try:
            fields = analyze_pdf_bytes(proceso.pdf_data)
            resultado = fields.get("resultado")
            if resultado:
                proceso.resultado = resultado
                proceso.error_message = None
            else:
                proceso.resultado = None
                proceso.error_message = "No se pudo determinar el resultado del PDF."
        except Exception:
            proceso.resultado = None
            proceso.error_message = _format_error()

        db.session.commit()


def process_img_to_pdf_job(job_id: int, image_paths: list[str]) -> None:
    app = create_app()
    with app.app_context():
        job = ImgToPdfJob.query.get(job_id)
        if not job:
            return

        try:
            job.status = "processing"
            db.session.commit()

            pdf_bytes, page_count = create_pdf_from_files(image_paths)
            job.pdf_data = pdf_bytes
            job.page_count = page_count
            job.pdf_filename = job.filename
            job.status = "done"
            job.error_message = None
            _cleanup_img_pdf_files(image_paths)
        except Exception as exc:
            job.status = "error"
            job.error_message = _format_img_pdf_error(exc)
            _cleanup_img_pdf_files(image_paths)

        db.session.commit()


def _cleanup_img_pdf_files(image_paths: list[str]) -> None:
    if not image_paths:
        return
    base_dir = Path("debug/img_to_pdf").resolve()
    parents = set()
    for value in image_paths:
        try:
            resolved = Path(value).resolve()
        except FileNotFoundError:
            continue
        if resolved == base_dir or base_dir not in resolved.parents:
            continue
        parents.add(resolved.parent)
    for parent in parents:
        if parent == base_dir or base_dir not in parent.parents:
            continue
        try:
            shutil.rmtree(parent, ignore_errors=True)
        except Exception:
            pass


def _format_error() -> str:
    detail = traceback.format_exc()
    if not detail:
        return "Error desconocido en el proceso RPA."
    return detail[-1200:]


def _format_img_pdf_error(exc: Exception) -> str:
    detail = str(exc or "")
    if "No se pudo leer la imagen" in detail:
        return "No se pudo leer una de las imagenes. Verifica el formato."
    if "No se recibieron imágenes" in detail or "No se recibieron imagenes" in detail:
        return "No se recibieron imagenes validas para generar el PDF."
    if "No se pudo codificar la imagen" in detail:
        return "No se pudo procesar una imagen. Intenta con otra foto."
    return "No se pudo generar el PDF. Intenta nuevamente."
