from flask import jsonify, request, abort
from flask_login import login_required, current_user
from . import api_bp
from ...extensions import db
from ...services.analytics_service import AnalyticsService
from ...services.notification_service import NotificationService
from ...services.grade_service import GradeService
from ...services.attendance_service import AttendanceService
from ...repositories.user_repository import UserRepository
from ...utils.helpers import active_school_year

analytics = AnalyticsService()
notif_service = NotificationService()
grade_service = GradeService()
att_service = AttendanceService()
user_repo = UserRepository()


@api_bp.route("/dashboard/stats")
@login_required
def dashboard_stats():
    if current_user.role != "director":
        abort(403)
    school_year = active_school_year()
    stats = analytics.get_director_stats(
        school_year_id=school_year.id if school_year else None
    )
    return jsonify(stats)


@api_bp.route("/subjects/averages")
@login_required
def subjects_averages():
    """Média global por disciplina (para o dashboard da direção)."""
    from ...models.grade import Grade
    from ...models.class_ import ClassSubject
    from ...models.subject import Subject
    school_year = active_school_year()
    stmt = (
        db.select(Subject.name.label("subject"), db.func.avg(Grade.score).label("avg"))
        .select_from(ClassSubject)
        .join(Grade, Grade.class_subject_id == ClassSubject.id)
        .join(Subject, Subject.id == ClassSubject.subject_id)
    )
    if school_year:
        stmt = stmt.where(ClassSubject.school_year_id == school_year.id)
    stmt = stmt.group_by(Subject.id, Subject.name).order_by(Subject.name)
    rows = db.session.execute(stmt).all()
    return jsonify([{"subject": r.subject, "avg": round(float(r.avg), 2)} for r in rows])


@api_bp.route("/classes/<int:class_id>/performance")
@login_required
def class_performance(class_id):
    school_year = active_school_year()
    if not school_year:
        return jsonify([])
    data = analytics.get_class_performance_chart(class_id, school_year.id)
    return jsonify(data)


@api_bp.route("/students/<int:student_id>/performance")
@login_required
def student_performance(student_id):
    school_year = active_school_year()
    if not school_year:
        return jsonify([])
    data = analytics.get_student_performance_chart(student_id, school_year.id)
    return jsonify(data)


@api_bp.route("/students/<int:student_id>/attendance")
@login_required
def student_attendance(student_id):
    school_year = active_school_year()
    data = analytics.get_student_attendance_chart(
        student_id, school_year.id if school_year else None
    )
    return jsonify(data)


@api_bp.route("/students/<int:student_id>/evolution")
@login_required
def student_grade_evolution(student_id):
    """Evolução de notas por bimestre para gráfico de linha multi-série."""
    from ...models.grade import Grade
    from ...models.class_ import ClassSubject
    from ...models.subject import Subject
    from ...models.school_year import GradePeriod
    from sqlalchemy import func
    from collections import defaultdict

    school_year = active_school_year()
    if not school_year:
        return jsonify({"periods": [], "series": []})

    periods = db.session.execute(
        db.select(GradePeriod)
        .where(GradePeriod.school_year_id == school_year.id)
        .order_by(GradePeriod.order_index)
    ).scalars().all()

    if not periods:
        return jsonify({"periods": [], "series": []})

    period_names = [p.name for p in periods]
    pid_to_name = {p.id: p.name for p in periods}

    rows = db.session.execute(
        db.select(
            Subject.name.label("subject"),
            Grade.grade_period_id,
            func.avg(Grade.score).label("avg"),
        )
        .select_from(ClassSubject)
        .join(Grade, Grade.class_subject_id == ClassSubject.id)
        .join(Subject, Subject.id == ClassSubject.subject_id)
        .where(
            Grade.student_id == student_id,
            ClassSubject.school_year_id == school_year.id,
        )
        .group_by(ClassSubject.subject_id, Grade.grade_period_id)
    ).all()

    subject_data = defaultdict(dict)
    for r in rows:
        pname = pid_to_name.get(r.grade_period_id)
        if pname:
            subject_data[r.subject][pname] = round(float(r.avg), 1)

    series = sorted(
        [
            {"label": subj, "data": [subject_data[subj].get(p) for p in period_names]}
            for subj in subject_data
        ],
        key=lambda x: x["label"],
    )
    return jsonify({"periods": period_names, "series": series})


@api_bp.route("/classes/averages")
@login_required
def classes_averages():
    """Média geral por turma — comparativo entre turmas."""
    from ...models.grade import Grade
    from ...models.class_ import ClassSubject, Class
    school_year = active_school_year()
    stmt = (
        db.select(Class.name.label("class_name"), db.func.avg(Grade.score).label("avg"))
        .select_from(ClassSubject)
        .join(Grade, Grade.class_subject_id == ClassSubject.id)
        .join(Class, Class.id == ClassSubject.class_id)
    )
    if school_year:
        stmt = stmt.where(ClassSubject.school_year_id == school_year.id)
    stmt = stmt.group_by(Class.id, Class.name).order_by(Class.name)
    rows = db.session.execute(stmt).all()
    return jsonify([{"class": r.class_name, "avg": round(float(r.avg), 2)} for r in rows])


@api_bp.route("/attendance/by-class")
@login_required
def attendance_by_class():
    """Taxa de presença por turma."""
    from ...models.attendance import AttendanceRecord, AttendanceSession
    from ...models.class_ import ClassSubject, Class
    from sqlalchemy import func
    school_year = active_school_year()
    stmt = (
        db.select(
            Class.name.label("class_name"),
            func.count(AttendanceRecord.id).label("total"),
            func.sum(db.case((AttendanceRecord.status == "present", 1), else_=0)).label("presences"),
        )
        .select_from(ClassSubject)
        .join(AttendanceSession, AttendanceSession.class_subject_id == ClassSubject.id)
        .join(AttendanceRecord, AttendanceRecord.session_id == AttendanceSession.id)
        .join(Class, Class.id == ClassSubject.class_id)
    )
    if school_year:
        stmt = stmt.where(ClassSubject.school_year_id == school_year.id)
    stmt = stmt.group_by(Class.id, Class.name).order_by(Class.name)
    rows = db.session.execute(stmt).all()
    result = []
    for r in rows:
        pct = round(r.presences / r.total * 100, 1) if r.total else 0
        result.append({"class": r.class_name, "pct": pct})
    return jsonify(result)


@api_bp.route("/grades/evolution")
@login_required
def grades_evolution():
    """Evolução da média por bimestre, uma linha por turma."""
    from ...models.grade import Grade
    from ...models.class_ import ClassSubject, Class
    from ...models.school_year import GradePeriod
    from sqlalchemy import func
    from collections import defaultdict
    school_year = active_school_year()
    if not school_year:
        return jsonify({"periods": [], "series": []})

    periods = db.session.execute(
        db.select(GradePeriod)
        .where(GradePeriod.school_year_id == school_year.id)
        .order_by(GradePeriod.order_index)
    ).scalars().all()
    if not periods:
        return jsonify({"periods": [], "series": []})

    period_names = [p.name for p in periods]
    pid_to_name = {p.id: p.name for p in periods}

    rows = db.session.execute(
        db.select(
            Class.name.label("class_name"),
            Grade.grade_period_id,
            func.avg(Grade.score).label("avg"),
        )
        .select_from(ClassSubject)
        .join(Grade, Grade.class_subject_id == ClassSubject.id)
        .join(Class, Class.id == ClassSubject.class_id)
        .where(ClassSubject.school_year_id == school_year.id)
        .group_by(Class.id, Grade.grade_period_id)
        .order_by(Class.name)
    ).all()

    class_data = defaultdict(dict)
    for r in rows:
        pname = pid_to_name.get(r.grade_period_id)
        if pname:
            class_data[r.class_name][pname] = round(float(r.avg), 1)

    series = [
        {"label": cls, "data": [class_data[cls].get(p) for p in period_names]}
        for cls in sorted(class_data)
    ]
    return jsonify({"periods": period_names, "series": series})


@api_bp.route("/notifications/unread")
@login_required
def notifications_unread():
    count = notif_service.count_unread(current_user.id)
    notifications = notif_service.get_for_user(current_user.id, limit=10)
    return jsonify({
        "count": count,
        "notifications": [
            {
                "id": n.id,
                "title": n.title,
                "message": n.message,
                "type": n.type,
                "is_read": n.is_read,
                "created_at": n.created_at.isoformat(),
                "related_url": n.related_url,
            }
            for n in notifications
        ],
    })


@api_bp.route("/notifications/mark-read", methods=["POST"])
@login_required
def notifications_mark_read():
    notif_service.mark_all_read(current_user.id)
    return jsonify({"status": "ok"})


@api_bp.route("/attendance/bulk-save", methods=["POST"])
@login_required
def attendance_bulk_save():
    data = request.get_json()
    if not data:
        return jsonify({"error": "dados inválidos"}), 400
    try:
        from datetime import date
        session_date = date.fromisoformat(data["date"])
        att_service.take_attendance(
            class_id=data["class_id"],
            class_subject_id=data["class_subject_id"],
            teacher_id=current_user.id,
            session_date=session_date,
            records=data["records"],
            lesson_number=data.get("lesson_number", 1),
        )
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.route("/grades/bulk-save", methods=["POST"])
@login_required
def grades_bulk_save():
    data = request.get_json()
    if not data:
        return jsonify({"error": "dados inválidos"}), 400
    try:
        entries = data.get("grades", [])
        grade_service.save_bulk_grades(entries)
        return jsonify({"status": "ok", "saved": len(entries)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
