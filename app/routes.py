import io
import os
import re
import secrets

from datetime import datetime

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
from .models import ImgToPdfJob, User, Workspace
from .queue import get_queue
from .services.img_to_pdf import build_previews, save_previews_to_folder


main = Blueprint("main", __name__)


def _safe_filename(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("_")


def _wants_json() -> bool:
    if request.headers.get("X-Requested-With") == "fetch":
        return True
    accept = request.headers.get("Accept", "")
    return "application/json" in accept


def _require_admin():
    if current_user.role != "admin":
        flash("No tienes permisos para acceder a esta seccion.", "error")
        return redirect(url_for("main.dashboard"))
    return None


@main.route("/")
@login_required
def dashboard():
    img_jobs = (
        ImgToPdfJob.query.filter_by(workspace_id=current_user.workspace_id)
        .order_by(ImgToPdfJob.created_at.desc())
        .limit(5)
        .all()
    )
    return render_template("dashboard.html", img_jobs=img_jobs)


@main.route("/tools/img-to-pdf")
@login_required
def img_to_pdf():
    jobs = (
        ImgToPdfJob.query.filter_by(workspace_id=current_user.workspace_id)
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
        workspace_id=current_user.workspace_id,
        created_by_user_id=current_user.id,
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
        ImgToPdfJob.query.filter_by(workspace_id=current_user.workspace_id)
        .order_by(ImgToPdfJob.created_at.desc())
        .all()
    )
    has_pending = any(job.status in {"queued", "processing", "pending"} for job in jobs)
    html = render_template("partials/img_to_pdf_rows.html", jobs=jobs)
    return jsonify({"html": html, "has_pending": has_pending})


@main.route("/tools/img-to-pdf/<int:job_id>/download")
@login_required
def img_to_pdf_download(job_id):
    job = ImgToPdfJob.query.filter_by(
        id=job_id, workspace_id=current_user.workspace_id
    ).first()
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
    job = ImgToPdfJob.query.filter_by(
        id=job_id, workspace_id=current_user.workspace_id
    ).first()
    if not job or not job.pdf_data:
        flash("El PDF aun no esta disponible.", "error")
        return redirect(url_for("main.img_to_pdf"))

    return send_file(
        io.BytesIO(job.pdf_data),
        mimetype="application/pdf",
        download_name=job.pdf_filename or job.filename,
        as_attachment=False,
    )


@main.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    workspace = getattr(current_user, "workspace", None) or Workspace.query.first()

    if request.method == "POST":
        form_type = request.form.get("form_type", "workspace")
        if form_type == "workspace":
            workspace_name = request.form.get("workspace_name", "").strip()
            if not workspace_name:
                flash("El nombre del workspace es obligatorio.", "error")
                return redirect(url_for("main.settings"))
            if workspace:
                workspace.name = workspace_name
                db.session.commit()
                flash("Nombre del workspace actualizado.", "success")
                return redirect(url_for("main.settings"))
            workspace = Workspace(name=workspace_name)
            db.session.add(workspace)
            db.session.commit()
            flash("Workspace creado.", "success")
            return redirect(url_for("main.settings"))

        return redirect(url_for("main.settings"))

    return render_template(
        "settings.html",
        workspace_name=workspace.name if workspace else "",
    )


@main.route("/control-panel", methods=["GET", "POST"])
@login_required
def control_panel():
    guard = _require_admin()
    if guard:
        return guard

    workspace_id = current_user.workspace_id

    if request.method == "POST":
        action = request.form.get("action", "")
        if action == "create_user":
            username = (request.form.get("username") or "").strip()
            first_name = (request.form.get("first_name") or "").strip()
            last_name = (request.form.get("last_name") or "").strip()
            role = (request.form.get("role") or "user").strip().lower()
            password = (request.form.get("password") or "").strip()

            if not username:
                flash("El usuario es obligatorio.", "error")
                return redirect(url_for("main.control_panel"))
            if User.query.filter_by(username=username).first():
                flash("Ese usuario ya existe.", "error")
                return redirect(url_for("main.control_panel"))

            if not password:
                flash("Ingresa una contraseña o usa el generador.", "error")
                return redirect(url_for("main.control_panel"))

            new_user = User(
                username=username,
                first_name=first_name,
                last_name=last_name,
                role="admin" if role == "admin" else "user",
                is_active=True,
                workspace_id=workspace_id,
            )
            new_user.set_password(password)
            db.session.add(new_user)
            db.session.commit()
            flash("Usuario creado correctamente.", "success")

        elif action == "update_user":
            user_id = request.form.get("user_id", type=int)
            if not user_id:
                flash("Usuario invalido.", "error")
                return redirect(url_for("main.control_panel"))
            user = User.query.filter_by(id=user_id, workspace_id=workspace_id).first()
            if not user:
                flash("Usuario no encontrado.", "error")
                return redirect(url_for("main.control_panel"))

            user.first_name = (request.form.get("first_name") or "").strip()
            user.last_name = (request.form.get("last_name") or "").strip()
            role = (request.form.get("role") or "user").strip().lower()
            user.role = "admin" if role == "admin" else "user"
            user.is_active = request.form.get("is_active") == "on"
            new_password = (request.form.get("new_password") or "").strip()

            if user.id == current_user.id and not user.is_active:
                user.is_active = True
                flash("No puedes desactivar tu propio usuario.", "error")
            else:
                flash("Usuario actualizado.", "success")

            if new_password:
                user.set_password(new_password)
                flash(
                    f"Contraseña para {user.username}: {new_password}",
                    "success persistent",
                )

            db.session.commit()

        elif action == "reset_password":
            user_id = request.form.get("user_id", type=int)
            if not user_id:
                flash("Usuario invalido.", "error")
                return redirect(url_for("main.control_panel"))
            user = User.query.filter_by(id=user_id, workspace_id=workspace_id).first()
            if not user:
                flash("Usuario no encontrado.", "error")
                return redirect(url_for("main.control_panel"))

            reset_mode = request.form.get("reset_mode", "manual")
            new_password = (request.form.get("new_password") or "").strip()
            if reset_mode == "random" or not new_password:
                new_password = secrets.token_urlsafe(9)

            user.set_password(new_password)
            db.session.commit()
            flash("Contraseña actualizada.", "success")
            flash(
                f"Contraseña para {user.username}: {new_password}",
                "success persistent",
            )

        return redirect(url_for("main.control_panel"))

    users = (
        User.query.filter_by(workspace_id=workspace_id)
        .order_by(User.created_at.asc())
        .all()
    )

    return render_template(
        "control_panel.html",
        users=users,
    )
