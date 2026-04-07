from datetime import datetime, timezone
from ..extensions import db


class Message(db.Model):
    __tablename__ = "messages"

    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    subject = db.Column(db.String(200))
    body = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    sent_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    parent_message_id = db.Column(db.Integer, db.ForeignKey("messages.id"), nullable=True)

    sender = db.relationship("User", foreign_keys=[sender_id], back_populates="sent_messages")
    recipient = db.relationship("User", foreign_keys=[recipient_id], back_populates="received_messages")
    replies = db.relationship("Message", backref=db.backref("parent", remote_side=[id]), lazy="dynamic")

    def __repr__(self):
        return f"<Message from={self.sender_id} to={self.recipient_id}>"
