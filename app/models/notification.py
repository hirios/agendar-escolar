from datetime import datetime, timezone
from ..extensions import db


class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    type = db.Column(
        db.Enum(
            "attendance_alert", "grade_alert", "assignment", "general",
            name="notification_type",
        ),
        default="general",
    )
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    related_url = db.Column(db.String(300))

    user = db.relationship("User", foreign_keys=[user_id], back_populates="notifications")

    TYPE_ICONS = {
        "attendance_alert": "exclamation-triangle",
        "grade_alert": "academic-cap",
        "assignment": "clipboard-list",
        "general": "bell",
    }

    @property
    def icon(self):
        return self.TYPE_ICONS.get(self.type, "bell")

    def __repr__(self):
        return f"<Notification user={self.user_id} type={self.type}>"
