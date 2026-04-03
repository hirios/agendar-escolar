from ..extensions import db
from ..models.notification import Notification
from .base_repository import BaseRepository


class NotificationRepository(BaseRepository):
    def __init__(self):
        super().__init__(Notification)

    def get_for_user(self, user_id, limit=20):
        return self.session.execute(
            db.select(Notification)
            .where(Notification.user_id == user_id)
            .order_by(Notification.created_at.desc())
            .limit(limit)
        ).scalars().all()

    def count_unread(self, user_id):
        return self.session.execute(
            db.select(db.func.count(Notification.id)).where(
                Notification.user_id == user_id,
                Notification.is_read == False,
            )
        ).scalar() or 0

    def mark_all_read(self, user_id):
        self.session.execute(
            db.update(Notification)
            .where(Notification.user_id == user_id, Notification.is_read == False)
            .values(is_read=True)
        )
        self.session.commit()

    def create_for_user(self, user_id, title, message, type="general", related_url=None):
        n = Notification(
            user_id=user_id,
            title=title,
            message=message,
            type=type,
            related_url=related_url,
        )
        self.session.add(n)
        self.session.commit()
        return n
