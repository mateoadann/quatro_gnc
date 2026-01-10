import io
import math
import os
import re

from datetime import datetime, timedelta

from flask import (
    Blueprint,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask import current_app
from flask_login import current_user, login_required

from .extensions import db
from .models import EnargasCredentials, ImgToPdfJob, Proceso, Taller
from .queue import get_queue
from .services.rpa_session import get_status as get_rpa_session_status
from .services.img_to_pdf import build_previews, save_previews_to_folder

from sqlalchemy import func, or_
from sqlalchemy.orm import joinedload


main = Blueprint("main", __name__)

PATENTE_PATTERN = re.compile(r"^(?:[A-Z]{3}\d{3}|[A-Z]{2}\d{3}[A-Z]{2})$")


def _normalize_patente(raw_value):
    cleaned = re.sub(r"[^A-Za-z0-9]", "", raw_value)
    return cleaned.upper()


def _is_valid_patente(value):
    return bool(PATENTE_PATTERN.match(value))


def _safe_filename(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("_")


def _paginate_query(query, page: int, per_page: int):
    total = query.count()
    total_pages = max(math.ceil(total / per_page), 1)
    page = max(1, min(page, total_pages))
    items = query.limit(per_page).offset((page - 1) * per_page).all()
    return items, page, total_pages, total


def _paginate_query_no_count(query, page: int, per_page: int):
    total = query.count()
    total_pages = max(math.ceil(total / per_page), 1)
    page = max(1, min(page, total_pages))
    items = query.limit(per_page).offset((page - 1) * per_page).all()
    return items, page, total_pages, total


def _wants_json() -> bool:
    if request.headers.get("X-Requested-With") == "fetch":
        return True
    accept = request.headers.get("Accept", "")
    return "application/json" in accept


def _render_proceso_row(proceso):
    talleres = (
        Taller.query.filter_by(user_id=proceso.user_id)
        .order_by(Taller.nombre.asc())
        .all()
    )
    return render_template(
        "partials/rpa_enargas_rows.html",
        procesos=[proceso],
        stale_ids=set(),
        talleres=talleres,
    )


def _mark_stale_processes(user_id: int | None = None) -> int:
    minutes = current_app.config.get("RPA_STALE_MINUTES", 15)
    if minutes <= 0:
        return 0

    threshold = datetime.utcnow() - timedelta(minutes=minutes)
    query = Proceso.query.filter(Proceso.estado == "en proceso")
    if user_id is not None:
        query = query.filter(Proceso.user_id == user_id)

    stale_filter = or_(
        Proceso.updated_at < threshold,
        (Proceso.updated_at.is_(None) & (Proceso.created_at < threshold)),
    )
    query = query.filter(stale_filter)
    updated = query.update(
        {
            Proceso.estado: "error",
            Proceso.resultado: None,
            Proceso.error_message: "Tiempo de espera agotado. Reintentar.",
            Proceso.updated_at: datetime.utcnow(),
        },
        synchronize_session=False,
    )
    if updated:
        db.session.commit()
    return updated


@main.route("/")
@login_required
def dashboard():
    img_jobs = (
        ImgToPdfJob.query.order_by(ImgToPdfJob.created_at.desc()).limit(5).all()
    )
    procesos = Proceso.query.order_by(Proceso.created_at.desc()).limit(5).all()
    return render_template("dashboard.html", img_jobs=img_jobs, procesos=procesos)


@main.route("/tools/img-to-pdf")
@login_required
def img_to_pdf():
    jobs = (
        ImgToPdfJob.query.filter_by(user_id=current_user.id)
        .order_by(ImgToPdfJob.created_at.desc())
        .all()
    )
    return render_template("img_to_pdf.html", jobs=jobs)


def _render_img_job_row(job):
    return render_template("partials/img_to_pdf_rows.html", jobs=[job])


@main.route("/tools/img-to-pdf/preview", methods=["POST"])
@login_required
def img_to_pdf_preview():
    files = request.files.getlist("images")
    if not files:
        return jsonify({"error": "Debes subir al menos una imagen."}), 400

    enhance_mode = request.form.get("enhance_mode", "soft")
    file_keys = request.form.getlist("file_keys") or None
    try:
        previews = build_previews(files, enhance_mode=enhance_mode, file_keys=file_keys)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception:
        return jsonify({"error": "No se pudo procesar las imagenes."}), 500

    return jsonify({"previews": previews})


@main.route("/tools/img-to-pdf/generate", methods=["POST"])
@login_required
def img_to_pdf_generate():
    payload = request.get_json(silent=True) or {}
    images = payload.get("images") or []
    filename = payload.get("filename") or ""

    if not images:
        return jsonify({"error": "No se recibieron imagenes para generar el PDF."}), 400

    safe_name = _safe_filename(filename) if filename else ""
    if safe_name:
        if not safe_name.lower().endswith(".pdf"):
            safe_name = f"{safe_name}.pdf"
    else:
        safe_name = f"imagenes_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.pdf"

    job = ImgToPdfJob(
        user_id=current_user.id,
        filename=safe_name,
        status="queued",
        page_count=0,
    )
    db.session.add(job)
    db.session.commit()

    folder = os.path.join("debug", "img_to_pdf", str(job.id))
    try:
        image_paths = save_previews_to_folder(images, folder)
    except ValueError as exc:
        db.session.delete(job)
        db.session.commit()
        return jsonify({"error": str(exc)}), 400
    except Exception:
        db.session.delete(job)
        db.session.commit()
        return jsonify({"error": "No se pudieron preparar las imagenes."}), 500

    queue = get_queue()
    queue.enqueue("app.tasks.process_img_to_pdf_job", job.id, image_paths)

    row_html = _render_img_job_row(job)
    return jsonify({"job_id": job.id, "row_html": row_html})


@main.route("/tools/img-to-pdf/table")
@login_required
def img_to_pdf_table():
    jobs = (
        ImgToPdfJob.query.filter_by(user_id=current_user.id)
        .order_by(ImgToPdfJob.created_at.desc())
        .all()
    )
    has_pending = any(job.status in {"queued", "processing", "pending"} for job in jobs)
    html = render_template("partials/img_to_pdf_rows.html", jobs=jobs)
    return jsonify({"html": html, "has_pending": has_pending})


@main.route("/tools/img-to-pdf/<int:job_id>/download")
@login_required
def img_to_pdf_download(job_id):
    job = ImgToPdfJob.query.filter_by(id=job_id, user_id=current_user.id).first()
    if not job or not job.pdf_data:
        flash("El PDF aun no esta disponible.", "error")
        return redirect(url_for("main.img_to_pdf"))

    return send_file(
        io.BytesIO(job.pdf_data),
        mimetype="application/pdf",
        download_name=job.pdf_filename or job.filename,
        as_attachment=True,
    )


@main.route("/tools/img-to-pdf/<int:job_id>/view")
@login_required
def img_to_pdf_view(job_id):
    job = ImgToPdfJob.query.filter_by(id=job_id, user_id=current_user.id).first()
    if not job or not job.pdf_data:
        flash("El PDF aun no esta disponible.", "error")
        return redirect(url_for("main.img_to_pdf"))

    return send_file(
        io.BytesIO(job.pdf_data),
        mimetype="application/pdf",
        download_name=job.pdf_filename or job.filename,
        as_attachment=False,
    )


@main.route("/tools/rpa-enargas", methods=["GET", "POST"])
@login_required
def rpa_enargas():
    if request.method == "POST":
        patente = _normalize_patente(request.form.get("patente", ""))
        if not _is_valid_patente(patente):
            message = "La patente debe ser AAA123 o AA123AA (con o sin guiones/espacios)."
            if _wants_json():
                return jsonify({"error": message}), 400
            flash(message, "error")
            return redirect(url_for("main.rpa_enargas"))

        credentials = EnargasCredentials.query.filter_by(user_id=current_user.id).first()
        if not credentials:
            message = "Carga las credenciales de Enargas antes de ejecutar."
            if _wants_json():
                return jsonify({"error": message}), 400
            flash(message, "error")
            return redirect(url_for("main.settings"))
        if not credentials.get_password():
            message = "Completa la contrasena de Enargas antes de ejecutar."
            if _wants_json():
                return jsonify({"error": message}), 400
            flash(message, "error")
            return redirect(url_for("main.settings"))

        taller_id = request.form.get("taller_id", "")
        taller_name = request.form.get("taller_name", "").strip()

        existing = (
            Proceso.query.filter_by(user_id=current_user.id, patente=patente)
            .filter(Proceso.taller_id.isnot(None))
            .order_by(Proceso.created_at.desc())
            .first()
        )
        selected_taller = None
        taller_created = False
        if existing and existing.taller_id:
            selected_taller = Taller.query.filter_by(
                id=existing.taller_id, user_id=current_user.id
            ).first()
        if existing and existing.taller_id and not selected_taller:
            existing = None

        if not existing:
            if not taller_id:
                message = "Selecciona o crea un taller antes de continuar."
                if _wants_json():
                    return jsonify({"error": message}), 400
                flash(message, "error")
                return redirect(url_for("main.rpa_enargas"))

            if taller_id == "new":
                if not taller_name:
                    message = "Ingresa el nombre del taller."
                    if _wants_json():
                        return jsonify({"error": message}), 400
                    flash(message, "error")
                    return redirect(url_for("main.rpa_enargas"))
                selected_taller = Taller.query.filter_by(
                    user_id=current_user.id, nombre=taller_name
                ).first()
                if not selected_taller:
                    selected_taller = Taller(
                        user_id=current_user.id,
                        nombre=taller_name,
                    )
                    db.session.add(selected_taller)
                    db.session.flush()
                    taller_created = True
            else:
                try:
                    selected_taller = Taller.query.filter_by(
                        id=int(taller_id), user_id=current_user.id
                    ).first()
                except ValueError:
                    selected_taller = None

                if not selected_taller:
                    message = "El taller seleccionado no es valido."
                    if _wants_json():
                        return jsonify({"error": message}), 400
                    flash(message, "error")
                    return redirect(url_for("main.rpa_enargas"))

        proceso = Proceso(
            user_id=current_user.id,
            taller_id=selected_taller.id if selected_taller else None,
            patente=patente,
            estado="en proceso",
        )
        if selected_taller:
            proceso.taller = selected_taller
        db.session.add(proceso)
        db.session.commit()

        _enqueue_rpa_async(proceso.id)
        if _wants_json():
            return jsonify(
                {
                    "proceso_id": proceso.id,
                    "row_html": _render_proceso_row(proceso),
                    "taller_id": selected_taller.id if selected_taller else None,
                    "taller_nombre": selected_taller.nombre if selected_taller else None,
                    "taller_created": taller_created,
                }
            )
        flash("Proceso en cola. Se actualizara cuando finalice.", "success")
        return redirect(url_for("main.rpa_enargas"))

    _mark_stale_processes(current_user.id)
    page = request.args.get("page", 1, type=int)
    per_page = current_app.config.get("RPA_PER_PAGE", 10)
    stale_minutes = current_app.config.get("RPA_STALE_MINUTES", 15)
    filters = _parse_filters(request.args)
    query = (
        Proceso.query.filter(Proceso.user_id == current_user.id)
        .outerjoin(Taller)
        .options(joinedload(Proceso.taller))
    )
    query = _apply_filters(query, filters)
    query = _apply_sort(query, filters)
    procesos, page, total_pages, _total = _paginate_query(query, page, per_page)
    has_pending = (
        db.session.query(Proceso.id)
        .filter(Proceso.user_id == current_user.id, Proceso.estado == "en proceso")
        .first()
        is not None
    )
    stale_ids = _get_stale_ids(procesos, minutes=stale_minutes)
    talleres = (
        Taller.query.filter_by(user_id=current_user.id)
        .order_by(Taller.nombre.asc())
        .all()
    )
    filter_params = _build_filter_params(filters)
    total_count = _total
    return render_template(
        "rpa_enargas.html",
        procesos=procesos,
        has_pending=has_pending,
        stale_ids=stale_ids,
        page=page,
        total_pages=total_pages,
        total_count=total_count,
        filter_params=filter_params,
        filters=filters,
        talleres=talleres,
    )


@main.route("/tools/rpa-enargas/table")
@login_required
def rpa_enargas_table():
    _mark_stale_processes(current_user.id)
    page = request.args.get("page", 1, type=int)
    per_page = current_app.config.get("RPA_PER_PAGE", 10)
    stale_minutes = current_app.config.get("RPA_STALE_MINUTES", 15)
    filters = _parse_filters(request.args)
    query = (
        Proceso.query.filter(Proceso.user_id == current_user.id)
        .outerjoin(Taller)
        .options(joinedload(Proceso.taller))
    )
    query = _apply_filters(query, filters)
    query = _apply_sort(query, filters)
    procesos, page, total_pages, total = _paginate_query_no_count(query, page, per_page)
    has_pending = (
        db.session.query(Proceso.id)
        .filter(Proceso.user_id == current_user.id, Proceso.estado == "en proceso")
        .first()
        is not None
    )
    stale_ids = _get_stale_ids(procesos, minutes=stale_minutes)
    talleres = (
        Taller.query.filter_by(user_id=current_user.id)
        .order_by(Taller.nombre.asc())
        .all()
    )
    html = render_template(
        "partials/rpa_enargas_rows.html",
        procesos=procesos,
        stale_ids=stale_ids,
        talleres=talleres,
    )
    pagination = render_template(
        "partials/rpa_pagination.html",
        page=page,
        total_pages=total_pages,
        filter_params=_build_filter_params(filters),
    )
    return jsonify(
        {
            "html": html,
            "has_pending": has_pending,
            "pagination": pagination,
            "total": total,
            "page": page,
            "total_pages": total_pages,
        }
    )


@main.route("/tools/rpa-enargas/session-status")
@login_required
def rpa_enargas_session_status():
    return jsonify(get_rpa_session_status())



@main.route("/tools/rpa-enargas/<int:proceso_id>/retry", methods=["POST"])
@login_required
def rpa_enargas_retry(proceso_id):
    proceso = Proceso.query.filter_by(id=proceso_id, user_id=current_user.id).first()
    if not proceso:
        message = "Proceso no encontrado."
        if _wants_json():
            return jsonify({"error": message}), 404
        flash(message, "error")
        return redirect(url_for("main.rpa_enargas"))

    proceso.estado = "en proceso"
    proceso.resultado = None
    proceso.pdf_data = None
    proceso.pdf_filename = None
    proceso.error_message = None
    db.session.commit()

    _enqueue_rpa_async(proceso.id)
    if _wants_json():
        return jsonify(
            {
                "proceso_id": proceso.id,
                "row_html": _render_proceso_row(proceso),
            }
        )
    flash("Proceso reencolado.", "success")
    return redirect(url_for("main.rpa_enargas"))


@main.route("/tools/rpa-enargas/<int:proceso_id>/taller", methods=["POST"])
@login_required
def rpa_enargas_update_taller(proceso_id):
    payload = request.get_json(silent=True) or {}
    raw_taller_id = payload.get("taller_id")
    proceso = Proceso.query.filter_by(id=proceso_id, user_id=current_user.id).first()
    if not proceso:
        return jsonify({"error": "Proceso no encontrado."}), 404

    if proceso.estado == "en proceso":
        return jsonify({"error": "No se puede editar un proceso en curso."}), 400

    if raw_taller_id in (None, "", 0, "0"):
        proceso.taller_id = None
        db.session.commit()
        return jsonify({"taller_id": None, "taller_nombre": "Sin taller"})

    try:
        taller_id = int(raw_taller_id)
    except (TypeError, ValueError):
        return jsonify({"error": "Taller invalido."}), 400

    taller = Taller.query.filter_by(id=taller_id, user_id=current_user.id).first()
    if not taller:
        return jsonify({"error": "Taller no encontrado."}), 404

    proceso.taller_id = taller.id
    db.session.commit()
    return jsonify({"taller_id": taller.id, "taller_nombre": taller.nombre})

@main.route("/tools/rpa-enargas/delete", methods=["POST"])
@login_required
def rpa_enargas_delete():
    payload = request.get_json(silent=True) or {}
    raw_ids = payload.get("ids", [])
    if not isinstance(raw_ids, list) or not raw_ids:
        return jsonify({"error": "Selecciona al menos un proceso."}), 400

    ids = []
    for value in raw_ids:
        try:
            ids.append(int(value))
        except (TypeError, ValueError):
            continue

    if not ids:
        return jsonify({"error": "Selecciona al menos un proceso."}), 400

    procesos = (
        Proceso.query.filter(Proceso.user_id == current_user.id)
        .filter(Proceso.id.in_(ids))
        .all()
    )
    if not procesos:
        return jsonify({"error": "No se encontraron procesos para eliminar."}), 404

    for proceso in procesos:
        db.session.delete(proceso)

    db.session.commit()
    return jsonify({"deleted": len(procesos)})


def _get_stale_ids(procesos, minutes=10):
    threshold = datetime.utcnow() - timedelta(minutes=minutes)
    return {
        proceso.id
        for proceso in procesos
        if proceso.estado == "en proceso"
        and proceso.updated_at
        and proceso.updated_at < threshold
    }


@main.route("/tools/rpa-enargas/<int:proceso_id>/pdf")
@login_required
def rpa_enargas_pdf(proceso_id):
    return _send_proceso_pdf(proceso_id, as_attachment=True)


@main.route("/tools/rpa-enargas/<int:proceso_id>/preview")
@login_required
def rpa_enargas_preview(proceso_id):
    return _send_proceso_pdf(proceso_id, as_attachment=False)


def _send_proceso_pdf(proceso_id, as_attachment):
    proceso = Proceso.query.filter_by(id=proceso_id, user_id=current_user.id).first()
    if not proceso or not proceso.pdf_data:
        flash("No hay PDF disponible para este proceso.", "error")
        return redirect(url_for("main.rpa_enargas"))

    filename = proceso.pdf_filename or f"proceso_{proceso.id}.pdf"
    return send_file(
        io.BytesIO(proceso.pdf_data),
        mimetype="application/pdf",
        as_attachment=as_attachment,
        download_name=filename,
    )


def _enqueue_rpa_async(proceso_id):
    try:
        queue = get_queue()
        queue.enqueue("app.tasks.process_rpa_job", proceso_id)
    except Exception:
        proceso = Proceso.query.get(proceso_id)
        if not proceso:
            return
        proceso.estado = "error"
        proceso.resultado = None
        proceso.pdf_data = None
        proceso.pdf_filename = None
        proceso.error_message = "No se pudo encolar el proceso."
        db.session.commit()


def _parse_filters(args):
    filters = {
        "query": (args.get("f_query") or "").strip(),
        "estado": (args.get("f_estado") or "").strip(),
        "resultado": (args.get("f_resultado") or "").strip(),
        "date_from": (args.get("f_date_from") or "").strip(),
        "date_to": (args.get("f_date_to") or "").strip(),
        "sort": (args.get("sort") or "fecha").strip(),
        "dir": (args.get("dir") or "desc").strip(),
    }
    return filters


def _build_filter_params(filters):
    params = {}
    if filters.get("query"):
        params["f_query"] = filters["query"]
    if filters.get("estado"):
        params["f_estado"] = filters["estado"]
    if filters.get("resultado"):
        params["f_resultado"] = filters["resultado"]
    if filters.get("date_from"):
        params["f_date_from"] = filters["date_from"]
    if filters.get("date_to"):
        params["f_date_to"] = filters["date_to"]
    if filters.get("sort"):
        params["sort"] = filters["sort"]
    if filters.get("dir"):
        params["dir"] = filters["dir"]
    return params


def _apply_filters(query, filters):
    if filters["query"]:
        cleaned = _normalize_patente(filters["query"])
        like_query = f"%{filters['query']}%"
        like_patente = f"%{cleaned}%"
        query = query.filter(
            or_(
                Proceso.patente.ilike(like_patente),
                Taller.nombre.ilike(like_query),
            )
        )
    if filters["estado"]:
        query = query.filter(Proceso.estado.ilike(f"%{filters['estado']}%"))
    if filters["resultado"]:
        query = query.filter(Proceso.resultado.ilike(f"%{filters['resultado']}%"))

    if filters["date_from"]:
        try:
            start = datetime.strptime(filters["date_from"], "%Y-%m-%d")
            query = query.filter(Proceso.created_at >= start)
        except ValueError:
            pass
    if filters["date_to"]:
        try:
            end = datetime.strptime(filters["date_to"], "%Y-%m-%d") + timedelta(days=1)
            query = query.filter(Proceso.created_at < end)
        except ValueError:
            pass

    return query


def _apply_sort(query, filters):
    sort_key = filters.get("sort") or "fecha"
    direction = (filters.get("dir") or "desc").lower()
    is_desc = direction != "asc"

    sort_map = {
        "fecha": Proceso.created_at,
        "patente": Proceso.patente,
    }
    column = sort_map.get(sort_key, Proceso.created_at)
    if is_desc:
        return query.order_by(column.desc())
    return query.order_by(column.asc())


@main.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    credentials = EnargasCredentials.query.filter_by(user_id=current_user.id).first()

    if request.method == "POST":
        enargas_user = request.form.get("enargas_user", "").strip()
        enargas_password = request.form.get("enargas_password", "").strip()
        if not enargas_user:
            flash("El usuario de Enargas es obligatorio.", "error")
            return redirect(url_for("main.settings"))

        if not credentials:
            if not enargas_password:
                flash("La contrasena de Enargas es obligatoria.", "error")
                return redirect(url_for("main.settings"))
            credentials = EnargasCredentials(
                user_id=current_user.id,
                enargas_user=enargas_user,
            )
            credentials.set_password(enargas_password)
            db.session.add(credentials)
        else:
            credentials.enargas_user = enargas_user
            if enargas_password:
                credentials.set_password(enargas_password)

        db.session.commit()
        flash("Configuracion actualizada.", "success")
        return redirect(url_for("main.settings"))

    masked_password = ""
    if credentials:
        password_value = credentials.get_password()
        if password_value:
            masked_password = (
                f"{password_value[:4]}{'*' * max(len(password_value) - 4, 0)}"
            )

    return render_template(
        "settings.html",
        credentials=credentials,
        masked_password=masked_password,
    )
