import calendar
from datetime import date, datetime, timezone
from flask import render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from . import teacher_bp
from ...utils.decorators import teacher_required
from ...services.attendance_service import AttendanceService
from ...services.grade_service import GradeService
from ...services.analytics_service import AnalyticsService
from ...repositories.class_repository import ClassRepository
from ...repositories.grade_repository import GradeRepository
from ...repositories.attendance_repository import AttendanceRepository
from ...repositories.user_repository import UserRepository
from ...repositories.assignment_repository import AssignmentRepository
from ...models.class_ import ClassSubject, ClassStudent
from ...models.assignment import Assignment, AssignmentSubmission
from ...models.attendance import AttendanceSession, AttendanceRecord
from ...models.message import Message
from ...models.school_year import SchoolYear, GradePeriod
from ...utils.helpers import active_school_year
from ...extensions import db

att_service = AttendanceService()
grade_service = GradeService()
analytics_service = AnalyticsService()
class_repo = ClassRepository()
grade_repo = GradeRepository()
att_repo = AttendanceRepository()
user_repo = UserRepository()
assignment_repo = AssignmentRepository()


@teacher_bp.route("/")
@login_required
@teacher_required
def dashboard():
    school_year = active_school_year()
    class_subjects = []
    stats = {"students": 0, "upcoming_assignments": 0, "at_risk": 0}
    cs_stats = {"students_per_class": {}, "avg_per_cs": {}, "last_att_per_cs": {}}
    upcoming_assignments = []
    at_risk = []
    if school_year:
        class_subjects = class_repo.get_teacher_class_subjects(
            current_user.id, school_year.id
        )
        stats = analytics_service.get_teacher_stats(current_user.id, school_year.id)
        cs_stats = analytics_service.get_teacher_class_subject_stats(current_user.id, school_year.id)
        upcoming_assignments = analytics_service.get_upcoming_assignments(current_user.id, school_year.id)
        at_risk = analytics_service.get_teacher_at_risk_students(current_user.id, school_year.id)
    today = date.today()
    return render_template(
        "teacher/dashboard.html",
        class_subjects=class_subjects,
        school_year=school_year,
        today=today,
        stats=stats,
        cs_stats=cs_stats,
        upcoming_assignments=upcoming_assignments,
        at_risk=at_risk,
    )


@teacher_bp.route("/classes/")
@login_required
@teacher_required
def class_list():
    school_year = active_school_year()
    classes = class_repo.get_teacher_classes(
        current_user.id, school_year.id if school_year else None
    )
    return render_template("teacher/classes/list.html", classes=classes, school_year=school_year)


@teacher_bp.route("/classes/<int:class_id>")
@login_required
@teacher_required
def class_detail(class_id):
    class_ = class_repo.get_by_id(class_id)
    if not class_:
        abort(404)
    school_year = active_school_year()
    # Verifica se o professor está associado a essa turma
    my_class_subjects = class_repo.get_teacher_class_subjects(
        current_user.id, school_year.id if school_year else None
    )
    my_cs_ids = {cs.class_id for cs in my_class_subjects}
    if class_id not in my_cs_ids and current_user.role != "director":
        abort(403)
    students = user_repo.get_students_by_class(class_id)
    subject_class_subjects = [cs for cs in my_class_subjects if cs.class_id == class_id]
    return render_template(
        "teacher/classes/detail.html",
        class_=class_,
        students=students,
        subject_class_subjects=subject_class_subjects,
        school_year=school_year,
    )


# ── Chamada ───────────────────────────────────────────────────────────────────

@teacher_bp.route("/attendance/<int:cs_id>")
@login_required
@teacher_required
def attendance_history(cs_id):
    cs = db.session.get(ClassSubject, cs_id)
    if not cs or (cs.teacher_id != current_user.id and current_user.role != "director"):
        abort(403)
    sessions = att_service.get_sessions_for_class_subject(cs_id)
    return render_template("teacher/attendance/history.html", cs=cs, sessions=sessions)


@teacher_bp.route("/attendance/<int:cs_id>/calendar")
@login_required
@teacher_required
def attendance_calendar(cs_id):
    cs = db.session.get(ClassSubject, cs_id)
    if not cs or (cs.teacher_id != current_user.id and current_user.role != "director"):
        abort(403)

    today = date.today()
    month = request.args.get("month", today.month, type=int)
    year = request.args.get("year", today.year, type=int)

    # Clamp month to valid range
    if month < 1:
        month = 12
        year -= 1
    elif month > 12:
        month = 1
        year += 1

    # Query all sessions for this cs_id in the given month/year
    from sqlalchemy import extract
    sessions = db.session.execute(
        db.select(AttendanceSession).where(
            AttendanceSession.class_subject_id == cs_id,
            extract("year", AttendanceSession.date) == year,
            extract("month", AttendanceSession.date) == month,
        )
    ).scalars().all()

    # Build calendar_data: {day: {total, absences, absent_students}}
    calendar_data = {}
    for session in sessions:
        day = session.date.day
        if day not in calendar_data:
            calendar_data[day] = {"total": 0, "absences": 0, "absent_students": []}
        for record in session.records:
            calendar_data[day]["total"] += 1
            if record.status == "absent":
                calendar_data[day]["absences"] += 1
                calendar_data[day]["absent_students"].append(record.student.name)

    # calendar.monthcalendar returns list of weeks; each week is [Mon..Sun] with 0 for days outside month
    cal_grid = calendar.monthcalendar(year, month)
    month_name = calendar.month_name[month]

    # Prev/next month for navigation
    if month == 1:
        prev_month, prev_year = 12, year - 1
    else:
        prev_month, prev_year = month - 1, year
    if month == 12:
        next_month, next_year = 1, year + 1
    else:
        next_month, next_year = month + 1, year

    return render_template(
        "teacher/attendance/calendar.html",
        cs=cs,
        month=month,
        year=year,
        month_name=month_name,
        cal_grid=cal_grid,
        calendar_data=calendar_data,
        today=today,
        prev_month=prev_month,
        prev_year=prev_year,
        next_month=next_month,
        next_year=next_year,
    )


@teacher_bp.route("/attendance/<int:cs_id>/take", methods=["GET", "POST"])
@login_required
@teacher_required
def attendance_take(cs_id):
    cs = db.session.get(ClassSubject, cs_id)
    if not cs or (cs.teacher_id != current_user.id and current_user.role != "director"):
        abort(403)
    students = user_repo.get_students_by_class(cs.class_id)

    if request.method == "POST":
        session_date_str = request.form.get("date", str(date.today()))
        session_date = date.fromisoformat(session_date_str)
        lesson_number = int(request.form.get("lesson_number", 1))
        records = []
        for student in students:
            status = request.form.get(f"status_{student.id}", "absent")
            justification = request.form.get(f"justification_{student.id}")
            records.append({
                "student_id": student.id,
                "status": status,
                "justification": justification,
            })
        att_service.take_attendance(
            class_id=cs.class_id,
            class_subject_id=cs_id,
            teacher_id=current_user.id,
            session_date=session_date,
            records=records,
            lesson_number=lesson_number,
        )
        flash("Chamada salva com sucesso!", "success")
        return redirect(url_for("teacher.attendance_history", cs_id=cs_id))

    today = date.today()
    return render_template("teacher/attendance/take.html", cs=cs, students=students, today=today)


# ── Notas ─────────────────────────────────────────────────────────────────────

@teacher_bp.route("/grades/<int:cs_id>")
@login_required
@teacher_required
def grades_overview(cs_id):
    cs = db.session.get(ClassSubject, cs_id)
    if not cs or (cs.teacher_id != current_user.id and current_user.role != "director"):
        abort(403)
    students = user_repo.get_students_by_class(cs.class_id)
    periods = db.session.execute(
        db.select(GradePeriod)
        .where(GradePeriod.school_year_id == cs.school_year_id)
        .order_by(GradePeriod.order_index)
    ).scalars().all()

    # Monta grade de notas: {student_id: {period_id: {grade_type: score}}}
    from ...models.grade import Grade
    all_grades = db.session.execute(
        db.select(Grade).where(Grade.class_subject_id == cs_id)
    ).scalars().all()
    grade_map = {}
    for g in all_grades:
        grade_map.setdefault(g.student_id, {}).setdefault(g.grade_period_id, {})[g.grade_type] = float(g.score)

    return render_template(
        "teacher/grades/overview.html",
        cs=cs,
        students=students,
        periods=periods,
        grade_map=grade_map,
    )


@teacher_bp.route("/grades/save", methods=["POST"])
@login_required
@teacher_required
def grades_save():
    data = request.get_json()
    if not data:
        return {"error": "dados inválidos"}, 400
    entries = data.get("grades", [])
    try:
        grade_service.save_bulk_grades(entries)
        return {"status": "ok", "saved": len(entries)}
    except Exception as e:
        return {"error": str(e)}, 500


# ── Atividades ────────────────────────────────────────────────────────────────

@teacher_bp.route("/assignments/")
@login_required
@teacher_required
def assignment_list():
    school_year = active_school_year()
    my_cs = class_repo.get_teacher_class_subjects(
        current_user.id, school_year.id if school_year else None
    )
    cs_ids = [cs.id for cs in my_cs]
    assignments = []
    if cs_ids:
        assignments = db.session.execute(
            db.select(Assignment)
            .where(Assignment.class_subject_id.in_(cs_ids))
            .order_by(Assignment.due_date)
        ).scalars().all()
    return render_template("teacher/assignments/list.html", assignments=assignments)


@teacher_bp.route("/assignments/new", methods=["GET", "POST"])
@login_required
@teacher_required
def assignment_new():
    school_year = active_school_year()
    my_cs = class_repo.get_teacher_class_subjects(
        current_user.id, school_year.id if school_year else None
    )
    if request.method == "POST":
        due = request.form.get("due_date")
        a = Assignment(
            class_subject_id=int(request.form["class_subject_id"]),
            teacher_id=current_user.id,
            title=request.form["title"].strip(),
            description=request.form.get("description"),
            due_date=datetime.fromisoformat(due) if due else None,
            max_score=float(request.form.get("max_score", 10)),
            type=request.form.get("type", "homework"),
        )
        db.session.add(a)
        db.session.commit()
        flash("Atividade criada!", "success")
        return redirect(url_for("teacher.assignment_list"))
    return render_template("teacher/assignments/form.html", class_subjects=my_cs, action="new")


@teacher_bp.route("/assignments/<int:assignment_id>/edit", methods=["GET", "POST"])
@login_required
@teacher_required
def assignment_edit(assignment_id):
    a = db.session.get(Assignment, assignment_id)
    if not a or a.teacher_id != current_user.id:
        abort(403)
    school_year = active_school_year()
    my_cs = class_repo.get_teacher_class_subjects(
        current_user.id, school_year.id if school_year else None
    )
    if request.method == "POST":
        due = request.form.get("due_date")
        a.title = request.form["title"].strip()
        a.description = request.form.get("description")
        a.due_date = datetime.fromisoformat(due) if due else None
        a.max_score = float(request.form.get("max_score", 10))
        a.type = request.form.get("type", "homework")
        db.session.commit()
        flash("Atividade atualizada!", "success")
        return redirect(url_for("teacher.assignment_list"))
    return render_template("teacher/assignments/form.html", assignment=a, class_subjects=my_cs, action="edit")


@teacher_bp.route("/assignments/<int:assignment_id>/submissions")
@login_required
@teacher_required
def assignment_submissions(assignment_id):
    a = db.session.get(Assignment, assignment_id)
    if not a or a.teacher_id != current_user.id:
        abort(403)

    # Get all active students in the assignment's class
    students = user_repo.get_students_by_class(a.class_subject.class_id)

    # Map student_id -> submission
    subs = db.session.execute(
        db.select(AssignmentSubmission).where(AssignmentSubmission.assignment_id == assignment_id)
    ).scalars().all()
    sub_map = {s.student_id: s for s in subs}

    submissions_data = []
    for student in students:
        submission = sub_map.get(student.id)
        # Determine display status
        if submission is None:
            display_status = "pending"
        elif submission.status == "graded":
            display_status = "graded"
        elif submission.submitted_at and a.due_date and submission.submitted_at > a.due_date:
            display_status = "late"
        else:
            display_status = "submitted"
        submissions_data.append({
            "student": student,
            "submission": submission,
            "display_status": display_status,
        })

    submitted_count = sum(1 for d in submissions_data if d["display_status"] != "pending")
    return render_template(
        "teacher/assignments/submissions.html",
        assignment=a,
        submissions_data=submissions_data,
        submitted_count=submitted_count,
        total_count=len(submissions_data),
    )


@teacher_bp.route("/assignments/<int:assignment_id>/grade", methods=["POST"])
@login_required
@teacher_required
def assignment_grade(assignment_id):
    a = db.session.get(Assignment, assignment_id)
    if not a or a.teacher_id != current_user.id:
        abort(403)

    data = request.get_json()
    if not data:
        return {"error": "dados inválidos"}, 400

    student_id = data.get("student_id")
    score = data.get("score")
    feedback = data.get("feedback", "")

    if student_id is None or score is None:
        return {"error": "student_id e score são obrigatórios"}, 400

    # Upsert submission
    sub = db.session.execute(
        db.select(AssignmentSubmission).where(
            AssignmentSubmission.assignment_id == assignment_id,
            AssignmentSubmission.student_id == student_id,
        )
    ).scalar_one_or_none()

    if sub:
        sub.score = score
        sub.feedback = feedback
        sub.status = "graded"
    else:
        sub = AssignmentSubmission(
            assignment_id=assignment_id,
            student_id=student_id,
            score=score,
            feedback=feedback,
            status="graded",
            submitted_at=datetime.now(timezone.utc),
        )
        db.session.add(sub)

    db.session.commit()
    return {"status": "ok"}


# ── Roster da Turma ───────────────────────────────────────────────────────────

@teacher_bp.route("/classes/<int:cs_id>/roster")
@login_required
@teacher_required
def class_roster(cs_id):
    cs = db.session.get(ClassSubject, cs_id)
    if not cs or (cs.teacher_id != current_user.id and current_user.role != "director"):
        abort(403)

    enrollments = db.session.execute(
        db.select(ClassStudent).where(
            ClassStudent.class_id == cs.class_id,
            ClassStudent.status == "active",
        )
    ).scalars().all()

    from flask import current_app
    from sqlalchemy import func
    from ...models.grade import Grade as GradeModel
    min_grade = current_app.config.get("MIN_PASSING_GRADE", 5.0)
    max_absent = current_app.config.get("MAX_ABSENCE_PERCENT", 25.0)

    students_data = []
    for enrollment in enrollments:
        student = enrollment.student
        avg_row = db.session.execute(
            db.select(func.avg(GradeModel.score))
            .where(GradeModel.class_subject_id == cs_id, GradeModel.student_id == student.id)
        ).scalar()
        avg_grade = round(float(avg_row), 1) if avg_row is not None else None

        _total, _absences, pct_absent = att_repo.get_student_rate(student.id, cs_id)

        score, reasons = analytics_service._compute_risk_score(avg_grade, pct_absent, min_grade, max_absent)

        if avg_grade is None:
            status = "sem_nota"
        elif avg_grade >= min_grade:
            status = "aprovado"
        elif avg_grade >= (min_grade - 2):
            status = "em_risco"
        else:
            status = "reprovado"

        students_data.append({
            "student": student,
            "avg_grade": avg_grade,
            "pct_absent": pct_absent,
            "score": score,
            "reasons": reasons,
            "status": status,
        })

    students_data.sort(key=lambda x: x["score"], reverse=True)

    graded = [s for s in students_data if s["avg_grade"] is not None]
    class_avg = round(sum(s["avg_grade"] for s in graded) / len(graded), 1) if graded else None
    at_risk_count = sum(1 for s in students_data if s["status"] in ("em_risco", "reprovado"))

    return render_template(
        "teacher/classes/roster.html",
        cs=cs,
        students_data=students_data,
        class_avg=class_avg,
        at_risk_count=at_risk_count,
        min_grade=min_grade,
    )


# ── Mensagens ─────────────────────────────────────────────────────────────────

@teacher_bp.route("/messages/")
@login_required
@teacher_required
def messages_inbox():
    inbox = current_user.received_messages.order_by(Message.sent_at.desc()).limit(50).all()
    return render_template("teacher/messages/inbox.html", inbox=inbox)


@teacher_bp.route("/messages/<int:message_id>/reply", methods=["POST"])
@login_required
@teacher_required
def messages_reply(message_id):
    original = db.session.get(Message, message_id)
    if not original or original.recipient_id != current_user.id:
        abort(403)
    body = request.form.get("body", "").strip()
    if not body:
        flash("A resposta não pode estar vazia.", "error")
        return redirect(url_for("teacher.messages_inbox"))
    original.is_read = True
    reply = Message(
        sender_id=current_user.id,
        recipient_id=original.sender_id,
        subject=f"Re: {original.subject or 'Sem assunto'}",
        body=body,
        parent_message_id=message_id,
    )
    db.session.add(reply)
    db.session.commit()
    flash("Resposta enviada!", "success")
    return redirect(url_for("teacher.messages_inbox"))
