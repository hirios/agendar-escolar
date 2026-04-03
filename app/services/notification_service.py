from ..repositories.notification_repository import NotificationRepository


class NotificationService:
    def __init__(self):
        self.repo = NotificationRepository()

    def create(self, user_id, title, message, type="general", related_url=None):
        return self.repo.create_for_user(
            user_id=user_id,
            title=title,
            message=message,
            type=type,
            related_url=related_url,
        )

    def get_for_user(self, user_id, limit=20):
        return self.repo.get_for_user(user_id, limit)

    def count_unread(self, user_id):
        return self.repo.count_unread(user_id)

    def mark_all_read(self, user_id):
        self.repo.mark_all_read(user_id)
