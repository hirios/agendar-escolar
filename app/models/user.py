from datetime import datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from ..extensions import db, login_manager


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(
        db.Enum("director", "teacher", "student", "parent", name="user_role"),
        nullable=False,
    )
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    __table_args__ = (
        db.CheckConstraint("trim(name) != ''", name="ck_users_name_not_blank"),
    )
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relacionamentos
    profile = db.relationship("UserProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    notifications = db.relationship("Notification", foreign_keys="Notification.user_id", back_populates="user", lazy="dynamic")
    sent_messages = db.relationship("Message", foreign_keys="Message.sender_id", back_populates="sender", lazy="dynamic")
    received_messages = db.relationship("Message", foreign_keys="Message.recipient_id", back_populates="recipient", lazy="dynamic")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def first_name(self):
        parts = self.name.split()
        return parts[0] if parts else ""

    @property
    def unread_notifications_count(self):
        return self.notifications.filter_by(is_read=False).count()

    @property
    def unread_messages_count(self):
        return self.received_messages.filter_by(is_read=False).count()

    def __repr__(self):
        return f"<User {self.email} ({self.role})>"


class UserProfile(db.Model):
    __tablename__ = "user_profiles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False)
    phone = db.Column(db.String(20))
    address = db.Column(db.Text)
    birth_date = db.Column(db.Date)
    avatar_url = db.Column(db.String(300))
    notes = db.Column(db.Text)

    user = db.relationship("User", back_populates="profile")


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))
