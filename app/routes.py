import io
import math
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


main = Blueprint("main", __name__)

PATENTE_PATTERN = re.compile(r"^(?:[A-Z]{3}\d{3}|[A-Z]{2}\d{3}[A-Z]{2})$")


def _normalize_patente(raw_value):
    cleaned = re.sub(r"[^A-Za-z0-9]", "", raw_value)
    return cleaned.upper()


def _is_valid_patente(value):
    return bool(PATENTE_PATTERN.match(value))


def _paginate_query(query, page: int, per_page: int):
    total = query.count()
    total_pages = max(math.ceil(total / per_page), 1)
    page = max(1, min(page, total_pages))
    items = query.limit(per_page).offset((page - 1) * per_page).all()
    return items, page, total_pages, total


def _paginate_query_no_count(query, page: int, per_page: int):
    page = max(page, 1)
    items = query.limit(per_page).offset((page - 1) * per_page).all()
    return items, page


def _wants_json() -> bool:
    if request.headers.get("X-Requested-With") == "fetch":
        return True
    accept = request.headers.get("Accept", "")
    return "application/json" in accept


def _render_proceso_row(proceso):
    return render_template(
        "partials/rpa_enargas_rows.html",
        procesos=[proceso],
        stale_ids=set(),
    )


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
    jobs = ImgToPdfJob.query.order_by(ImgToPdfJob.created_at.desc()).all()
    return render_template("img_to_pdf.html", jobs=jobs)


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

    page = request.args.get("page", 1, type=int)
    per_page = current_app.config.get("RPA_PER_PAGE", 10)
    query = Proceso.query.order_by(Proceso.created_at.desc())
    procesos, page, total_pages, _total = _paginate_query(query, page, per_page)
    has_pending = (
        db.session.query(Proceso.id)
        .filter(Proceso.estado == "en proceso")
        .first()
        is not None
    )
    stale_ids = _get_stale_ids(procesos, minutes=10)
    talleres = (
        Taller.query.filter_by(user_id=current_user.id)
        .order_by(Taller.nombre.asc())
        .all()
    )
    return render_template(
        "rpa_enargas.html",
        procesos=procesos,
        has_pending=has_pending,
        stale_ids=stale_ids,
        page=page,
        total_pages=total_pages,
        talleres=talleres,
    )


@main.route("/tools/rpa-enargas/table")
@login_required
def rpa_enargas_table():
    page = request.args.get("page", 1, type=int)
    per_page = current_app.config.get("RPA_PER_PAGE", 10)
    query = Proceso.query.order_by(Proceso.created_at.desc())
    procesos, page = _paginate_query_no_count(query, page, per_page)
    has_pending = (
        db.session.query(Proceso.id)
        .filter(Proceso.estado == "en proceso")
        .first()
        is not None
    )
    stale_ids = _get_stale_ids(procesos, minutes=10)
    html = render_template(
        "partials/rpa_enargas_rows.html",
        procesos=procesos,
        stale_ids=stale_ids,
    )
    return jsonify({"html": html, "has_pending": has_pending})


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
