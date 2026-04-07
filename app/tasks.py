from . import create_app
from .extensions import db
from .models import ImgToPdfJob
import traceback
from pathlib import Path
import shutil

from .services.img_to_pdf import create_pdf_from_files


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


def _format_img_pdf_error(exc: Exception) -> str:
    detail = str(exc or "")
    if "No se pudo leer la imagen" in detail:
        return "No se pudo leer una de las imagenes. Verifica el formato."
    if "No se recibieron imágenes" in detail or "No se recibieron imagenes" in detail:
        return "No se recibieron imagenes validas para generar el PDF."
    if "No se pudo codificar la imagen" in detail:
        return "No se pudo procesar una imagen. Intenta con otra foto."
    return "No se pudo generar el PDF. Intenta nuevamente."
