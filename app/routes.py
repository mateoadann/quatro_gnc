from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from .extensions import db
from .models import ImgToPdfJob, RpaEnargasJob


main = Blueprint("main", __name__)


@main.route("/")
@login_required
def dashboard():
    img_jobs = (
        ImgToPdfJob.query.order_by(ImgToPdfJob.created_at.desc()).limit(5).all()
    )
    rpa_jobs = (
        RpaEnargasJob.query.order_by(RpaEnargasJob.created_at.desc()).limit(5).all()
    )
    return render_template("dashboard.html", img_jobs=img_jobs, rpa_jobs=rpa_jobs)


@main.route("/tools/img-to-pdf")
@login_required
def img_to_pdf():
    jobs = ImgToPdfJob.query.order_by(ImgToPdfJob.created_at.desc()).all()
    return render_template("img_to_pdf.html", jobs=jobs)


@main.route("/tools/rpa-enargas")
@login_required
def rpa_enargas():
    jobs = RpaEnargasJob.query.order_by(RpaEnargasJob.created_at.desc()).all()
    return render_template("rpa_enargas.html", jobs=jobs)


@main.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    if request.method == "POST":
        enargas_user = request.form.get("enargas_user", "").strip()
        enargas_password = request.form.get("enargas_password", "").strip()
        current_user.enargas_user = enargas_user
        if enargas_password:
            current_user.set_enargas_password(enargas_password)
        db.session.commit()
        flash("Configuracion actualizada.", "success")
        return redirect(url_for("main.settings"))

    return render_template("settings.html")
