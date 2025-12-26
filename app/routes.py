import io
import re

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask_login import current_user, login_required

from .extensions import db
from .models import EnargasCredentials, ImgToPdfJob, Proceso
from .services.rpa_enargas import NoOperacionesError, run_rpa


main = Blueprint("main", __name__)

PATENTE_PATTERN = re.compile(r"^(?:[A-Z]{3}\\d{3}|[A-Z]{2}\\d{3}[A-Z]{2})$")


def _normalize_patente(raw_value):
    return raw_value.strip().upper()


def _is_valid_patente(value):
    return bool(PATENTE_PATTERN.match(value))


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
            flash(
                "La patente debe ser AAA123 o AA123AA.",
                "error",
            )
            return redirect(url_for("main.rpa_enargas"))

        credentials = EnargasCredentials.query.filter_by(user_id=current_user.id).first()
        if not credentials:
            flash("Carga las credenciales de Enargas antes de ejecutar.", "error")
            return redirect(url_for("main.settings"))
        if not credentials.get_password():
            flash("Completa la contrasena de Enargas antes de ejecutar.", "error")
            return redirect(url_for("main.settings"))

        proceso = Proceso(
            user_id=current_user.id,
            patente=patente,
            estado="en proceso",
        )
        db.session.add(proceso)
        db.session.commit()

        try:
            result = run_rpa(
                patente,
                credentials.enargas_user,
                credentials.get_password(),
            )
            proceso.estado = "completado"
            proceso.resultado = result.get("resultado")
            proceso.pdf_data = result.get("pdf_data")
            proceso.pdf_filename = result.get("pdf_filename")
            flash("Proceso completado.", "success")
        except NoOperacionesError:
            proceso.estado = "completado"
            proceso.resultado = "Patente NO registrada"
            proceso.pdf_data = None
            proceso.pdf_filename = None
            flash("Patente NO registrada en ENARGAS.", "warning")
        except Exception:
            proceso.estado = "error"
            proceso.resultado = None
            flash("Error al ejecutar el proceso RPA.", "error")

        db.session.commit()
        return redirect(url_for("main.rpa_enargas"))

    procesos = Proceso.query.order_by(Proceso.created_at.desc()).all()
    return render_template("rpa_enargas.html", procesos=procesos)


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
