import csv
import io
from flask import render_template, redirect, url_for, flash, request, abort, Response
from flask_login import login_required, current_user
from sqlalchemy import func
from . import director_bp
from ...utils.decorators import director_required
from ...services.auth_service import AuthService
from ...services.analytics_service import AnalyticsService
from ...services.grade_service import GradeService
from ...services.attendance_service import AttendanceService
from ...repositories.user_repository import UserRepository
from ...repositories.class_repository import ClassRepository
from ...repositories.attendance_repository import AttendanceRepository
from ...models.school_year import SchoolYear, GradePeriod
from ...models.subject import Subject
from ...models.class_ import Class, ClassSubject, ClassStudent
from ...models.calendar_event import CalendarEvent
from ...models.parent_student import ParentStudent
from ...models.attendance import AttendanceSession, AttendanceRecord
from ...models.grade import Grade
from ...models.user import User
from ...utils.helpers import active_school_year
from ...extensions import db

auth_service = AuthService()
analytics_service = AnalyticsService()
grade_service = GradeService()
att_service = AttendanceService()
user_repo = UserRepository()
class_repo = ClassRepository()


# ── Dashboard ──────────────────────────────────────────────────────────────────

@director_bp.route("/")
@login_required
@director_required
def dashboard():
    school_year = active_school_year()
    sy_id = school_year.id if school_year else None
    stats = analytics_service.get_director_stats(school_year_id=sy_id)
    at_risk = analytics_service.get_at_risk_with_scores(school_year_id=sy_id)
    overall_avg = analytics_service.get_overall_average(sy_id) if sy_id else None
    upcoming_events = analytics_service.get_upcoming_calendar_events(sy_id) if sy_id else []
    insights = analytics_service.get_insights(sy_id) if sy_id else []
    return render_template(
        "director/dashboard.html",
        stats=stats,
        at_risk=at_risk[:10],
        school_year=school_year,
        overall_avg=overall_avg,
        upcoming_events=upcoming_events,
        insights=insights,
    )


# ── Alunos ────────────────────────────────────────────────────────────────────

@director_bp.route("/students/")
@login_required
@director_required
def student_list():
    query = request.args.get("q", "")
    class_id = request.args.get("class_id", type=int)
    page = request.args.get("page", 1, type=int)
    show_inactive = request.args.get("inactive") == "1"
    students, total = user_repo.search(
        query=query, role="student", class_id=class_id, page=page,
        active_only=not show_inactive,
    )
    classes = class_repo.get_active()
    return render_template(
        "director/students/list.html",
        students=students,
        total=total,
        page=page,
        query=query,
        classes=classes,
        selected_class=class_id,
        show_inactive=show_inactive,
    )


@director_bp.route("/students/<int:student_id>")
@login_required
@director_required
def student_detail(student_id):
    student = user_repo.get_by_id(student_id)
    if not student or student.role != "student":
        abort(404)
    school_year = active_school_year()
    boletim = periods = None
    gpa = None
    attendance = []
    if school_year:
        boletim, periods = grade_service.get_boletim(student_id, school_year.id)
        gpa = grade_service.get_student_gpa(student_id, school_year.id)
        attendance = att_service.get_summary_for_student(student_id, school_year.id)
    return render_template(
        "director/students/detail.html",
        student=student,
        school_year=school_year,
        boletim=boletim,
        periods=periods,
        gpa=gpa,
        attendance=attendance,
    )


@director_bp.route("/students/new", methods=["GET", "POST"])
@login_required
@director_required
def student_new():
    classes = class_repo.get_active()
    if request.method == "POST":
        try:
            name = request.form["name"].strip()
            email = request.form["email"].strip().lower()
            password = request.form.get("password", "Escola@2025")
            profile_data = {
                "phone": request.form.get("phone"),
                "birth_date": request.form.get("birth_date") or None,
                "address": request.form.get("address"),
            }
            user = auth_service.create_user(name, email, password, "student", profile_data)
            class_id = request.form.get("class_id", type=int)
            if class_id:
                class_repo.enroll_student(class_id, user.id)
            flash(f"Aluno {name} cadastrado com sucesso!", "success")
            return redirect(url_for("director.student_detail", student_id=user.id))
        except ValueError as e:
            flash(str(e), "error")
    return render_template("director/students/form.html", classes=classes, action="new")


@director_bp.route("/students/<int:student_id>/edit", methods=["GET", "POST"])
@login_required
@director_required
def student_edit(student_id):
    student = user_repo.get_by_id(student_id)
    if not student or student.role != "student":
        abort(404)
    classes = class_repo.get_active()
    if request.method == "POST":
        name = request.form["name"].strip()
        if not name:
            flash("O nome não pode estar vazio.", "error")
            return render_template("director/students/form.html", student=student, classes=classes, action="edit")
        student.name = name
        if not student.profile:
            from ...models.user import UserProfile
            student.profile = UserProfile(user_id=student.id)
        student.profile.phone = request.form.get("phone")
        student.profile.address = request.form.get("address")
        birth = request.form.get("birth_date")
        if birth:
            from datetime import date
            student.profile.birth_date = date.fromisoformat(birth)
        db.session.commit()
        flash("Dados atualizados com sucesso!", "success")
        return redirect(url_for("director.student_detail", student_id=student.id))
    return render_template("director/students/form.html", student=student, classes=classes, action="edit")


@director_bp.route("/students/<int:student_id>/deactivate", methods=["POST"])
@login_required
@director_required
def student_deactivate(student_id):
    student = user_repo.get_by_id(student_id)
    if not student or student.role != "student":
        abort(404)
    user_repo.deactivate(student)
    flash(f"Aluno {student.name} desativado.", "info")
    return redirect(url_for("director.student_list"))


@director_bp.route("/students/<int:student_id>/reactivate", methods=["POST"])
@login_required
@director_required
def student_reactivate(student_id):
    student = user_repo.get_by_id(student_id)
    if not student or student.role != "student":
        abort(404)
    user_repo.reactivate(student)
    flash(f"Aluno {student.name} reativado.", "success")
    return redirect(url_for("director.student_list"))


# ── Professores ───────────────────────────────────────────────────────────────

@director_bp.route("/teachers/")
@login_required
@director_required
def teacher_list():
    show_inactive = request.args.get("inactive") == "1"
    teachers, _ = user_repo.search(role="teacher", query="", active_only=not show_inactive, per_page=200)
    return render_template("director/teachers/list.html", teachers=teachers, show_inactive=show_inactive)


@director_bp.route("/teachers/<int:teacher_id>")
@login_required
@director_required
def teacher_detail(teacher_id):
    teacher = user_repo.get_by_id(teacher_id)
    if not teacher or teacher.role != "teacher":
        abort(404)
    school_year = active_school_year()
    sy_id = school_year.id if school_year else None

    class_subjects = []
    cs_stats = {"students_per_class": {}, "avg_per_cs": {}, "last_att_per_cs": {}}
    at_risk = []
    sessions_count = 0

    if sy_id:
        class_subjects = class_repo.get_teacher_class_subjects(teacher.id, sy_id)
        cs_stats = analytics_service.get_teacher_class_subject_stats(teacher.id, sy_id)
        at_risk = analytics_service.get_teacher_at_risk_students(teacher.id, sy_id)

        cs_ids = [cs.id for cs in class_subjects]
        if cs_ids:
            sessions_count = db.session.execute(
                db.select(db.func.count(AttendanceSession.id))
                .where(AttendanceSession.class_subject_id.in_(cs_ids))
            ).scalar() or 0

    return render_template(
        "director/teachers/detail.html",
        teacher=teacher,
        school_year=school_year,
        class_subjects=class_subjects,
        cs_stats=cs_stats,
        at_risk=at_risk,
        sessions_count=sessions_count,
    )


@director_bp.route("/teachers/new", methods=["GET", "POST"])
@login_required
@director_required
def teacher_new():
    if request.method == "POST":
        try:
            name = request.form["name"].strip()
            email = request.form["email"].strip().lower()
            password = request.form.get("password", "Escola@2025")
            user = auth_service.create_user(name, email, password, "teacher")
            flash(f"Professor {name} cadastrado!", "success")
            return redirect(url_for("director.teacher_list"))
        except ValueError as e:
            flash(str(e), "error")
    return render_template("director/teachers/form.html", action="new")


@director_bp.route("/teachers/<int:teacher_id>/deactivate", methods=["POST"])
@login_required
@director_required
def teacher_deactivate(teacher_id):
    teacher = user_repo.get_by_id(teacher_id)
    if not teacher or teacher.role != "teacher":
        abort(404)
    user_repo.deactivate(teacher)
    flash(f"Professor {teacher.name} desativado.", "info")
    return redirect(url_for("director.teacher_list"))


@director_bp.route("/teachers/<int:teacher_id>/reactivate", methods=["POST"])
@login_required
@director_required
def teacher_reactivate(teacher_id):
    teacher = user_repo.get_by_id(teacher_id)
    if not teacher or teacher.role != "teacher":
        abort(404)
    user_repo.reactivate(teacher)
    flash(f"Professor {teacher.name} reativado.", "success")
    return redirect(url_for("director.teacher_list"))


@director_bp.route("/teachers/<int:teacher_id>/edit", methods=["GET", "POST"])
@login_required
@director_required
def teacher_edit(teacher_id):
    teacher = user_repo.get_by_id(teacher_id)
    if not teacher or teacher.role != "teacher":
        abort(404)
    if request.method == "POST":
        name = request.form["name"].strip()
        if not name:
            flash("O nome não pode estar vazio.", "error")
            return render_template("director/teachers/form.html", teacher=teacher, action="edit")
        teacher.name = name
        db.session.commit()
        flash("Professor atualizado!", "success")
        return redirect(url_for("director.teacher_list"))
    return render_template("director/teachers/form.html", teacher=teacher, action="edit")


# ── Turmas ────────────────────────────────────────────────────────────────────

@director_bp.route("/classes/")
@login_required
@director_required
def class_list():
    school_year = active_school_year()
    classes = class_repo.get_active(school_year_id=school_year.id if school_year else None)
    school_years = db.session.execute(db.select(SchoolYear).order_by(SchoolYear.name.desc())).scalars().all()
    return render_template(
        "director/classes/list.html",
        classes=classes,
        school_years=school_years,
        school_year=school_year,
    )


@director_bp.route("/classes/<int:class_id>")
@login_required
@director_required
def class_detail(class_id):
    class_ = class_repo.get_by_id(class_id)
    if not class_:
        abort(404)
    students = user_repo.get_students_by_class(class_id)
    all_students = user_repo.get_students()
    all_teachers = user_repo.get_teachers()
    all_subjects = db.session.execute(db.select(Subject).order_by(Subject.name)).scalars().all()
    school_year = active_school_year()
    performance = []
    if school_year:
        performance = grade_service.get_class_performance(class_id, school_year.id)
    return render_template(
        "director/classes/detail.html",
        class_=class_,
        students=students,
        all_students=all_students,
        all_teachers=all_teachers,
        all_subjects=all_subjects,
        performance=performance,
        school_year=school_year,
    )


@director_bp.route("/classes/new", methods=["GET", "POST"])
@login_required
@director_required
def class_new():
    school_years = db.session.execute(db.select(SchoolYear).order_by(SchoolYear.name.desc())).scalars().all()
    if request.method == "POST":
        class_ = Class(
            school_year_id=int(request.form["school_year_id"]),
            name=request.form["name"].strip(),
            grade_level=request.form.get("grade_level"),
            shift=request.form.get("shift", "morning"),
            room=request.form.get("room"),
            max_students=int(request.form.get("max_students", 40)),
        )
        db.session.add(class_)
        db.session.commit()
        flash(f"Turma {class_.name} criada!", "success")
        return redirect(url_for("director.class_detail", class_id=class_.id))
    return render_template("director/classes/form.html", school_years=school_years, action="new")


@director_bp.route("/classes/<int:class_id>/edit", methods=["GET", "POST"])
@login_required
@director_required
def class_edit(class_id):
    class_ = class_repo.get_by_id(class_id)
    if not class_:
        abort(404)
    school_years = db.session.execute(db.select(SchoolYear).order_by(SchoolYear.name.desc())).scalars().all()
    if request.method == "POST":
        class_.name = request.form["name"].strip()
        class_.grade_level = request.form.get("grade_level")
        class_.shift = request.form.get("shift", "morning")
        class_.room = request.form.get("room")
        class_.max_students = int(request.form.get("max_students", 40))
        db.session.commit()
        flash("Turma atualizada!", "success")
        return redirect(url_for("director.class_detail", class_id=class_.id))
    return render_template("director/classes/form.html", class_=class_, school_years=school_years, action="edit")


@director_bp.route("/classes/<int:class_id>/enroll", methods=["POST"])
@login_required
@director_required
def class_enroll(class_id):
    student_id = request.form.get("student_id", type=int)
    if student_id:
        class_repo.enroll_student(class_id, student_id)
        flash("Aluno matriculado!", "success")
    return redirect(url_for("director.class_detail", class_id=class_id))


@director_bp.route("/classes/<int:class_id>/remove-student", methods=["POST"])
@login_required
@director_required
def class_remove_student(class_id):
    student_id = request.form.get("student_id", type=int)
    if student_id:
        class_repo.remove_student(class_id, student_id)
        flash("Aluno removido da turma.", "info")
    return redirect(url_for("director.class_detail", class_id=class_id))


@director_bp.route("/classes/<int:class_id>/assign-teacher", methods=["POST"])
@login_required
@director_required
def class_assign_teacher(class_id):
    school_year = active_school_year()
    if not school_year:
        flash("Nenhum ano letivo ativo.", "error")
        return redirect(url_for("director.class_detail", class_id=class_id))
    subject_id = request.form.get("subject_id", type=int)
    teacher_id = request.form.get("teacher_id", type=int)
    if subject_id and teacher_id:
        class_repo.assign_teacher(class_id, subject_id, teacher_id, school_year.id)
        flash("Professor atribuído à disciplina!", "success")
    return redirect(url_for("director.class_detail", class_id=class_id))


# ── Disciplinas ───────────────────────────────────────────────────────────────

@director_bp.route("/subjects/")
@login_required
@director_required
def subject_list():
    subjects = db.session.execute(db.select(Subject).order_by(Subject.name)).scalars().all()
    return render_template("director/subjects/list.html", subjects=subjects)


@director_bp.route("/subjects/new", methods=["GET", "POST"])
@login_required
@director_required
def subject_new():
    if request.method == "POST":
        subj = Subject(
            name=request.form["name"].strip(),
            code=request.form["code"].strip().upper(),
            description=request.form.get("description"),
            workload_hours=request.form.get("workload_hours", type=int),
        )
        db.session.add(subj)
        db.session.commit()
        flash(f"Disciplina {subj.name} criada!", "success")
        return redirect(url_for("director.subject_list"))
    return render_template("director/subjects/form.html", action="new")


@director_bp.route("/subjects/<int:subject_id>/edit", methods=["GET", "POST"])
@login_required
@director_required
def subject_edit(subject_id):
    subj = db.session.get(Subject, subject_id)
    if not subj:
        abort(404)
    if request.method == "POST":
        subj.name = request.form["name"].strip()
        subj.code = request.form["code"].strip().upper()
        subj.description = request.form.get("description")
        subj.workload_hours = request.form.get("workload_hours", type=int)
        db.session.commit()
        flash("Disciplina atualizada!", "success")
        return redirect(url_for("director.subject_list"))
    return render_template("director/subjects/form.html", subject=subj, action="edit")


# ── Anos Letivos ──────────────────────────────────────────────────────────────

@director_bp.route("/school-years/")
@login_required
@director_required
def school_year_list():
    years = db.session.execute(db.select(SchoolYear).order_by(SchoolYear.name.desc())).scalars().all()
    return render_template("director/school_years/list.html", years=years)


@director_bp.route("/school-years/new", methods=["GET", "POST"])
@login_required
@director_required
def school_year_new():
    if request.method == "POST":
        from datetime import date
        sy = SchoolYear(
            name=request.form["name"].strip(),
            start_date=date.fromisoformat(request.form["start_date"]),
            end_date=date.fromisoformat(request.form["end_date"]),
        )
        if request.form.get("activate"):
            # Desativa o atual
            db.session.execute(db.update(SchoolYear).values(is_active=False))
            sy.is_active = True
        db.session.add(sy)
        db.session.commit()

        # Cria bimestres padrão
        periods = [
            ("1º Bimestre", 1), ("2º Bimestre", 2),
            ("3º Bimestre", 3), ("4º Bimestre", 4),
        ]
        for name, idx in periods:
            db.session.add(GradePeriod(school_year_id=sy.id, name=name, order_index=idx))
        db.session.commit()

        flash(f"Ano letivo {sy.name} criado!", "success")
        return redirect(url_for("director.school_year_list"))
    return render_template("director/school_years/form.html")


@director_bp.route("/school-years/<int:year_id>/activate", methods=["POST"])
@login_required
@director_required
def school_year_activate(year_id):
    db.session.execute(db.update(SchoolYear).values(is_active=False))
    sy = db.session.get(SchoolYear, year_id)
    if sy:
        sy.is_active = True
        db.session.commit()
        flash(f"Ano letivo {sy.name} ativado.", "success")
    return redirect(url_for("director.school_year_list"))


# ── Calendário ────────────────────────────────────────────────────────────────

@director_bp.route("/calendar/")
@login_required
@director_required
def calendar():
    school_year = active_school_year()
    events = []
    if school_year:
        events = db.session.execute(
            db.select(CalendarEvent)
            .where(CalendarEvent.school_year_id == school_year.id)
            .order_by(CalendarEvent.event_date)
        ).scalars().all()
    return render_template("director/calendar/index.html", events=events, school_year=school_year)


@director_bp.route("/calendar/new", methods=["GET", "POST"])
@login_required
@director_required
def calendar_new():
    from flask_login import current_user
    school_year = active_school_year()
    if request.method == "POST":
        from datetime import date
        ev = CalendarEvent(
            school_year_id=int(request.form["school_year_id"]),
            title=request.form["title"].strip(),
            description=request.form.get("description"),
            event_date=date.fromisoformat(request.form["event_date"]),
            end_date=date.fromisoformat(request.form["end_date"]) if request.form.get("end_date") else None,
            type=request.form.get("type", "event"),
            is_public=bool(request.form.get("is_public")),
            created_by=current_user.id,
        )
        db.session.add(ev)
        db.session.commit()
        flash("Evento adicionado ao calendário!", "success")
        return redirect(url_for("director.calendar"))
    school_years = db.session.execute(db.select(SchoolYear).order_by(SchoolYear.name.desc())).scalars().all()
    return render_template(
        "director/calendar/form.html",
        school_years=school_years,
        school_year=school_year,
    )


# ── Relatório Comparativo de Turmas ───────────────────────────────────────────

@director_bp.route("/reports/classes")
@login_required
@director_required
def report_classes():
    school_year = active_school_year()
    if not school_year:
        flash("Nenhum ano letivo ativo.", "error")
        return redirect(url_for("director.dashboard"))

    sy_id = school_year.id
    classes = class_repo.get_active(school_year_id=sy_id)

    classes_data = []
    for c in classes:
        n_students = db.session.execute(
            db.select(func.count(ClassStudent.id)).where(
                ClassStudent.class_id == c.id,
                ClassStudent.status == "active",
            )
        ).scalar() or 0

        avg_grade_raw = db.session.execute(
            db.select(func.avg(Grade.score))
            .join(ClassSubject, ClassSubject.id == Grade.class_subject_id)
            .where(ClassSubject.class_id == c.id, ClassSubject.school_year_id == sy_id)
        ).scalar()
        avg_grade = round(float(avg_grade_raw), 1) if avg_grade_raw is not None else None

        total_records = db.session.execute(
            db.select(func.count(AttendanceRecord.id))
            .join(AttendanceSession, AttendanceSession.id == AttendanceRecord.session_id)
            .where(AttendanceSession.class_id == c.id)
        ).scalar() or 0
        absent_records = db.session.execute(
            db.select(func.count(AttendanceRecord.id))
            .join(AttendanceSession, AttendanceSession.id == AttendanceRecord.session_id)
            .where(
                AttendanceSession.class_id == c.id,
                AttendanceRecord.status == "absent",
            )
        ).scalar() or 0
        pct_present = round((1 - absent_records / total_records) * 100, 1) if total_records > 0 else None

        n_subjects = db.session.execute(
            db.select(func.count(ClassSubject.id)).where(
                ClassSubject.class_id == c.id,
                ClassSubject.school_year_id == sy_id,
            )
        ).scalar() or 0

        student_ids = db.session.execute(
            db.select(ClassStudent.student_id).where(
                ClassStudent.class_id == c.id,
                ClassStudent.status == "active",
            )
        ).scalars().all()

        at_risk_count = 0
        for student_id in student_ids:
            s_avg_raw = db.session.execute(
                db.select(func.avg(Grade.score))
                .join(ClassSubject, ClassSubject.id == Grade.class_subject_id)
                .where(
                    ClassSubject.class_id == c.id,
                    ClassSubject.school_year_id == sy_id,
                    Grade.student_id == student_id,
                )
            ).scalar()
            s_avg = float(s_avg_raw) if s_avg_raw is not None else None

            s_total = db.session.execute(
                db.select(func.count(AttendanceRecord.id))
                .join(AttendanceSession, AttendanceSession.id == AttendanceRecord.session_id)
                .where(
                    AttendanceSession.class_id == c.id,
                    AttendanceRecord.student_id == student_id,
                )
            ).scalar() or 0
            s_absent = db.session.execute(
                db.select(func.count(AttendanceRecord.id))
                .join(AttendanceSession, AttendanceSession.id == AttendanceRecord.session_id)
                .where(
                    AttendanceSession.class_id == c.id,
                    AttendanceRecord.student_id == student_id,
                    AttendanceRecord.status == "absent",
                )
            ).scalar() or 0
            s_pct_absent = (s_absent / s_total * 100) if s_total > 0 else 0.0

            if (s_avg is not None and s_avg < 5.0) or s_pct_absent > 25.0:
                at_risk_count += 1

        classes_data.append({
            "class_": c,
            "n_students": n_students,
            "avg_grade": avg_grade,
            "pct_present": pct_present,
            "at_risk_count": at_risk_count,
            "n_subjects": n_subjects,
        })

    if request.args.get("export") == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Turma", "Alunos", "Média Geral", "% Presença", "Em Risco", "Disciplinas"])
        for d in classes_data:
            writer.writerow([
                d["class_"].name,
                d["n_students"],
                d["avg_grade"] if d["avg_grade"] is not None else "",
                d["pct_present"] if d["pct_present"] is not None else "",
                d["at_risk_count"],
                d["n_subjects"],
            ])
        output.seek(0)
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment; filename=turmas_{school_year.name}.csv"},
        )

    total_students = sum(d["n_students"] for d in classes_data)
    total_at_risk = sum(d["at_risk_count"] for d in classes_data)
    avgs = [d["avg_grade"] for d in classes_data if d["avg_grade"] is not None]
    overall_avg = round(sum(avgs) / len(avgs), 1) if avgs else None

    return render_template(
        "director/reports/classes.html",
        classes_data=classes_data,
        school_year=school_year,
        total_students=total_students,
        total_at_risk=total_at_risk,
        overall_avg=overall_avg,
    )


# ── Vínculo Responsável ↔ Aluno ───────────────────────────────────────────────

@director_bp.route("/students/<int:student_id>/parents")
@login_required
@director_required
def student_parents(student_id):
    student = user_repo.get_by_id(student_id)
    if not student or student.role != "student":
        abort(404)
    links = db.session.execute(
        db.select(ParentStudent).where(ParentStudent.student_id == student_id)
    ).scalars().all()
    return render_template(
        "director/students/parents.html",
        student=student,
        links=links,
    )


@director_bp.route("/students/<int:student_id>/parents/add", methods=["POST"])
@login_required
@director_required
def student_parents_add(student_id):
    student = user_repo.get_by_id(student_id)
    if not student or student.role != "student":
        abort(404)
    email = request.form.get("email", "").strip().lower()
    relationship = request.form.get("relationship", "responsável").strip()
    parent = db.session.execute(
        db.select(User).where(User.email == email, User.role == "parent")
    ).scalar_one_or_none()
    if not parent:
        flash("Responsável não encontrado ou e-mail não pertence a um usuário com papel 'responsável'.", "error")
        return redirect(url_for("director.student_parents", student_id=student_id))
    existing = db.session.execute(
        db.select(ParentStudent).where(
            ParentStudent.parent_id == parent.id,
            ParentStudent.student_id == student_id,
        )
    ).scalar_one_or_none()
    if existing:
        flash("Este responsável já está vinculado ao aluno.", "warning")
    else:
        link = ParentStudent(
            parent_id=parent.id,
            student_id=student_id,
            relationship=relationship or "responsável",
        )
        db.session.add(link)
        db.session.commit()
        flash(f"Responsável {parent.name} vinculado com sucesso!", "success")
    return redirect(url_for("director.student_parents", student_id=student_id))


@director_bp.route("/students/<int:student_id>/parents/remove/<int:parent_id>", methods=["POST"])
@login_required
@director_required
def student_parents_remove(student_id, parent_id):
    student = user_repo.get_by_id(student_id)
    if not student or student.role != "student":
        abort(404)
    link = db.session.execute(
        db.select(ParentStudent).where(
            ParentStudent.parent_id == parent_id,
            ParentStudent.student_id == student_id,
        )
    ).scalar_one_or_none()
    if link:
        db.session.delete(link)
        db.session.commit()
        flash("Vínculo removido.", "info")
    return redirect(url_for("director.student_parents", student_id=student_id))
