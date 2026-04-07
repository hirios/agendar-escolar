from ..repositories.user_repository import UserRepository
from ..models.user import User, UserProfile
from ..models.parent_student import ParentStudent
from ..extensions import db


class AuthService:
    def __init__(self):
        self.user_repo = UserRepository()

    def authenticate(self, email, password):
        user = self.user_repo.get_by_email(email)
        if user and user.is_active and user.check_password(password):
            return user
        return None

    def create_user(self, name, email, password, role, profile_data=None):
        if not name or not name.strip():
            raise ValueError("O nome não pode estar vazio.")
        if not email or not email.strip():
            raise ValueError("O e-mail não pode estar vazio.")
        if self.user_repo.get_by_email(email):
            raise ValueError("Email já cadastrado.")
        user = User(name=name, email=email, role=role)
        user.set_password(password)
        db.session.add(user)
        db.session.flush()  # para obter o ID

        profile = UserProfile(user_id=user.id)
        if profile_data:
            for key, value in profile_data.items():
                if hasattr(profile, key):
                    setattr(profile, key, value)
        db.session.add(profile)
        db.session.commit()
        return user

    def change_password(self, user, current_password, new_password):
        if not user.check_password(current_password):
            raise ValueError("Senha atual incorreta.")
        user.set_password(new_password)
        db.session.commit()

    def link_parent_student(self, parent_id, student_id, relationship="responsável"):
        existing = db.session.execute(
            db.select(ParentStudent).where(
                ParentStudent.parent_id == parent_id,
                ParentStudent.student_id == student_id,
            )
        ).scalar_one_or_none()
        if not existing:
            link = ParentStudent(
                parent_id=parent_id,
                student_id=student_id,
                relationship=relationship,
            )
            db.session.add(link)
            db.session.commit()
            return link
        return existing
