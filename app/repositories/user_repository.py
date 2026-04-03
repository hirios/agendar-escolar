from ..extensions import db
from ..models.user import User
from ..models.parent_student import ParentStudent
from .base_repository import BaseRepository


class UserRepository(BaseRepository):
    def __init__(self):
        super().__init__(User)

    def get_by_email(self, email):
        return self.filter_one(email=email)

    def get_by_role(self, role):
        return self.filter_by(role=role, is_active=True)

    def get_students(self):
        return self.filter_by(role="student", is_active=True)

    def get_teachers(self):
        return self.filter_by(role="teacher", is_active=True)

    def get_students_by_class(self, class_id):
        from ..models.class_ import ClassStudent
        result = self.session.execute(
            db.select(User)
            .join(ClassStudent, ClassStudent.student_id == User.id)
            .where(ClassStudent.class_id == class_id)
            .where(ClassStudent.status == "active")
            .order_by(User.name)
        ).scalars().all()
        return result

    def get_children_of_parent(self, parent_id):
        return self.session.execute(
            db.select(User)
            .join(ParentStudent, ParentStudent.student_id == User.id)
            .where(ParentStudent.parent_id == parent_id)
            .where(User.is_active == True)
        ).scalars().all()

    def search(self, query, role=None, class_id=None, page=1, per_page=20, active_only=True):
        from ..models.class_ import ClassStudent
        stmt = db.select(User)
        if active_only:
            stmt = stmt.where(User.is_active == True)
        if query:
            stmt = stmt.where(
                db.or_(
                    User.name.ilike(f"%{query}%"),
                    User.email.ilike(f"%{query}%"),
                )
            )
        if role:
            stmt = stmt.where(User.role == role)
        if class_id:
            stmt = stmt.join(ClassStudent, ClassStudent.student_id == User.id).where(
                ClassStudent.class_id == class_id, ClassStudent.status == "active"
            )
        total = self.session.execute(
            db.select(db.func.count()).select_from(stmt.subquery())
        ).scalar()
        items = self.session.execute(
            stmt.order_by(User.name).limit(per_page).offset((page - 1) * per_page)
        ).scalars().all()
        return items, total

    def deactivate(self, user):
        return self.update(user, is_active=False)

    def reactivate(self, user):
        return self.update(user, is_active=True)
