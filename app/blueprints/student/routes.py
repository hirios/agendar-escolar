from datetime import datetime, timezone
from flask import render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from . import student_bp
from ...utils.decorators import student_required
from ...services.grade_service import GradeService
from ...services.attendance_service import AttendanceService
from ...repositories.assignment_repository import AssignmentRepository
from ...models.schedule import Schedule
from ...models.class_ import ClassSubject, ClassStudent
from ...models.assignment import Assignment, AssignmentSubmission
from ...utils.helpers import active_school_year
from ...extensions import db

grade_service = GradeService()
att_service = AttendanceService()
assignment_repo = AssignmentRepository()


@student_bp.route("/")
@login_required
@student_required
def dashboard():
    school_year = active_school_year()
    gpa = None
    attendance_summary = []
    upcoming_assignments = []
    boletim = None
    periods = None

    if school_year:
        gpa = grade_service.get_student_gpa(current_user.id, school_year.id)
        attendance_summary = att_service.get_summary_for_student(current_user.id, school_year.id)
        upcoming_assignments = assignment_repo.get_for_student(current_user.id, school_year.id)[:5]
        boletim, periods = grade_service.get_boletim(current_user.id, school_year.id)

    return render_template(
        "student/dashboard.html",
        school_year=school_year,
        gpa=gpa,
        attendance_summary=attendance_summary,
        upcoming_assignments=upcoming_assignments,
        boletim=boletim,
        periods=periods,
    )


@student_bp.route("/grades/")
@login_required
@student_required
def grades():
    school_year = active_school_year()
    boletim = periods = None
    gpa = None
    if school_year:
        boletim, periods = grade_service.get_boletim(current_user.id, school_year.id)
        gpa = grade_service.get_student_gpa(current_user.id, school_year.id)
    return render_template(
        "student/grades.html",
        boletim=boletim,
        periods=periods,
        gpa=gpa,
        school_year=school_year,
    )


@student_bp.route("/attendance/")
@login_required
@student_required
def attendance():
    school_year = active_school_year()
    summary = []
    if school_year:
        summary = att_service.get_summary_for_student(current_user.id, school_year.id)
    return render_template("student/attendance.html", summary=summary, school_year=school_year)


@student_bp.route("/assignments/")
@login_required
@student_required
def assignments():
    school_year = active_school_year()
    all_assignments = []
    submissions = {}
    if school_year:
        all_assignments = assignment_repo.get_for_student(current_user.id, school_year.id)
        if all_assignments:
            assignment_ids = [a.id for a in all_assignments]
            subs = db.session.execute(
                db.select(AssignmentSubmission).where(
                    AssignmentSubmission.student_id == current_user.id,
                    AssignmentSubmission.assignment_id.in_(assignment_ids),
                )
            ).scalars().all()
            submissions = {s.assignment_id: s for s in subs}
    return render_template(
        "student/assignments.html",
        assignments=all_assignments,
        submissions=submissions,
        school_year=school_year,
    )


@student_bp.route("/assignments/<int:assignment_id>/submit", methods=["POST"])
@login_required
@student_required
def assignment_submit(assignment_id):
    a = db.session.get(Assignment, assignment_id)
    if not a:
        abort(404)

    # Verify the student is enrolled in the class for this assignment
    enrollment = db.session.execute(
        db.select(ClassStudent).where(
            ClassStudent.class_id == a.class_subject.class_id,
            ClassStudent.student_id == current_user.id,
            ClassStudent.status == "active",
        )
    ).scalar_one_or_none()
    if not enrollment:
        abort(403)

    now = datetime.now(timezone.utc)
    # Determine if late
    if a.due_date and now > a.due_date.replace(tzinfo=timezone.utc):
        status = "late"
    else:
        status = "submitted"

    # Upsert submission
    sub = db.session.execute(
        db.select(AssignmentSubmission).where(
            AssignmentSubmission.assignment_id == assignment_id,
            AssignmentSubmission.student_id == current_user.id,
        )
    ).scalar_one_or_none()

    if sub:
        if sub.status != "graded":
            sub.submitted_at = now
            sub.status = status
    else:
        sub = AssignmentSubmission(
            assignment_id=assignment_id,
            student_id=current_user.id,
            submitted_at=now,
            status=status,
        )
        db.session.add(sub)

    db.session.commit()

    if status == "late":
        flash("Atividade entregue (com atraso).", "warning")
    else:
        flash("Atividade entregue com sucesso!", "success")
    return redirect(url_for("student.assignments"))


@student_bp.route("/schedule/")
@login_required
@student_required
def schedule():
    school_year = active_school_year()
    schedules = []
    if school_year:
        enrollment = db.session.execute(
            db.select(ClassStudent)
            .where(ClassStudent.student_id == current_user.id, ClassStudent.status == "active")
        ).scalars().all()
        class_ids = [e.class_id for e in enrollment]
        if class_ids:
            cs_ids = db.session.execute(
                db.select(ClassSubject.id)
                .where(ClassSubject.class_id.in_(class_ids), ClassSubject.school_year_id == school_year.id)
            ).scalars().all()
            if cs_ids:
                schedules = db.session.execute(
                    db.select(Schedule)
                    .where(Schedule.class_subject_id.in_(cs_ids))
                    .order_by(Schedule.day_of_week, Schedule.start_time)
                ).scalars().all()
    return render_template("student/schedule.html", schedules=schedules, school_year=school_year)
