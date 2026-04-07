from datetime import datetime, timezone
from ..extensions import db


class CalendarEvent(db.Model):
    __tablename__ = "calendar_events"

    id = db.Column(db.Integer, primary_key=True)
    school_year_id = db.Column(db.Integer, db.ForeignKey("school_years.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    event_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date)
    type = db.Column(
        db.Enum("holiday", "exam", "meeting", "event", "deadline", name="event_type"),
        default="event",
    )
    is_public = db.Column(db.Boolean, default=True)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    school_year = db.relationship("SchoolYear", back_populates="calendar_events")
    creator = db.relationship("User", foreign_keys=[created_by])

    TYPE_LABELS = {
        "holiday": "Feriado",
        "exam": "Prova/Avaliação",
        "meeting": "Reunião",
        "event": "Evento",
        "deadline": "Prazo",
    }

    TYPE_COLORS = {
        "holiday": "red",
        "exam": "purple",
        "meeting": "blue",
        "event": "green",
        "deadline": "orange",
    }

    @property
    def type_label(self):
        return self.TYPE_LABELS.get(self.type, self.type)

    @property
    def type_color(self):
        return self.TYPE_COLORS.get(self.type, "gray")

    def __repr__(self):
        return f"<CalendarEvent {self.title} {self.event_date}>"
