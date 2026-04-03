from datetime import date
from flask import render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from . import parent_bp
from ...utils.decorators import parent_required
from ...repositories.user_repository import UserRepository
from ...services.grade_service import GradeService
from ...services.attendance_service import AttendanceService
from ...models.message import Message
from ...models.calendar_event import CalendarEvent
from ...utils.helpers import active_school_year
from ...extensions import db

user_repo = UserRepository()
grade_service = GradeService()
att_service = AttendanceService()


def _get_children():
    return user_repo.get_children_of_parent(current_user.id)


def _verify_child(student_id):
    children = _get_children()
    child = next((c for c in children if c.id == student_id), None)
    if not child:
        abort(403)
    return child


@parent_bp.route("/")
@login_required
@parent_required
def dashboard():
    children = _get_children()
    school_year = active_school_year()
    children_data = []
    for child in children:
        gpa = None
        att_summary = []
        if school_year:
            gpa = grade_service.get_student_gpa(child.id, school_year.id)
            att_summary = att_service.get_summary_for_student(child.id, school_year.id)
        children_data.append({"student": child, "gpa": gpa, "attendance": att_summary})
    return render_template("parent/dashboard.html", children_data=children_data, school_year=school_year)


@parent_bp.route("/child/<int:student_id>/grades")
@login_required
@parent_required
def child_grades(student_id):
    child = _verify_child(student_id)
    school_year = active_school_year()
    boletim = periods = None
    gpa = None
    if school_year:
        boletim, periods = grade_service.get_boletim(child.id, school_year.id)
        gpa = grade_service.get_student_gpa(child.id, school_year.id)
    return render_template(
        "parent/grades.html",
        student=child,
        boletim=boletim,
        periods=periods,
        gpa=gpa,
        school_year=school_year,
    )


@parent_bp.route("/child/<int:student_id>/attendance")
@login_required
@parent_required
def child_attendance(student_id):
    child = _verify_child(student_id)
    school_year = active_school_year()
    summary = []
    if school_year:
        summary = att_service.get_summary_for_student(child.id, school_year.id)
    return render_template("parent/attendance.html", student=child, summary=summary, school_year=school_year)


@parent_bp.route("/messages/")
@login_required
@parent_required
def messages():
    inbox = current_user.received_messages.order_by(Message.sent_at.desc()).limit(50).all()
    return render_template("parent/messages.html", inbox=inbox)


@parent_bp.route("/messages/<int:message_id>")
@login_required
@parent_required
def message_thread(message_id):
    msg = db.session.get(Message, message_id)
    if not msg:
        abort(404)
    # Verify current user is sender or recipient
    if msg.sender_id != current_user.id and msg.recipient_id != current_user.id:
        abort(403)

    # Find root message
    root = msg
    while root.parent_message_id is not None:
        root = db.session.get(Message, root.parent_message_id)

    # Mark as read if recipient
    if msg.recipient_id == current_user.id and not msg.is_read:
        msg.is_read = True
        db.session.commit()

    # Collect thread: root + all messages that share this root
    # Gather all messages that are replies to root or are root itself
    def collect_thread(root_msg):
        thread = [root_msg]
        stack = list(root_msg.replies.order_by(Message.sent_at).all())
        while stack:
            item = stack.pop(0)
            thread.append(item)
            stack.extend(item.replies.order_by(Message.sent_at).all())
        return thread

    thread = collect_thread(root)
    # Mark all unread messages in thread addressed to current user
    for t in thread:
        if t.recipient_id == current_user.id and not t.is_read:
            t.is_read = True
    db.session.commit()

    return render_template(
        "parent/messages/thread.html",
        thread=thread,
        root_message=root,
        message=msg,
    )


@parent_bp.route("/messages/<int:message_id>/reply", methods=["POST"])
@login_required
@parent_required
def message_reply(message_id):
    original = db.session.get(Message, message_id)
    if not original:
        abort(404)
    if original.sender_id != current_user.id and original.recipient_id != current_user.id:
        abort(403)

    body = request.form.get("body", "").strip()
    if not body:
        flash("A resposta não pode estar vazia.", "error")
        return redirect(url_for("parent.message_thread", message_id=message_id))

    # Determine the other party
    other_id = original.sender_id if original.recipient_id == current_user.id else original.recipient_id

    # Find root for parent_message_id
    root = original
    while root.parent_message_id is not None:
        root = db.session.get(Message, root.parent_message_id)

    reply = Message(
        sender_id=current_user.id,
        recipient_id=other_id,
        subject=f"Re: {root.subject or 'Sem assunto'}",
        body=body,
        parent_message_id=root.id,
    )
    db.session.add(reply)
    db.session.commit()
    flash("Resposta enviada!", "success")
    return redirect(url_for("parent.message_thread", message_id=root.id))


@parent_bp.route("/calendar/")
@login_required
@parent_required
def calendar():
    today = date.today()
    events = db.session.execute(
        db.select(CalendarEvent)
        .where(CalendarEvent.is_public == True, CalendarEvent.event_date >= today)
        .order_by(CalendarEvent.event_date)
    ).scalars().all()
    return render_template("parent/calendar.html", events=events, today=today)


@parent_bp.route("/messages/send", methods=["POST"])
@login_required
@parent_required
def send_message():
    recipient_id = request.form.get("recipient_id", type=int)
    subject = request.form.get("subject", "").strip()
    body = request.form.get("body", "").strip()
    if not body or not recipient_id:
        flash("Mensagem ou destinatário inválido.", "error")
        return redirect(url_for("parent.messages"))
    recipient = user_repo.get_by_id(recipient_id)
    if not recipient:
        abort(404)
    msg = Message(
        sender_id=current_user.id,
        recipient_id=recipient_id,
        subject=subject or "Sem assunto",
        body=body,
    )
    db.session.add(msg)
    db.session.commit()
    flash("Mensagem enviada!", "success")
    return redirect(url_for("parent.messages"))
