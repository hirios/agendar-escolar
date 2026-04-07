"""
BaseRepository — camada de abstração de banco de dados.

Todos os repositories herdam desta classe. Para trocar de banco de dados
(SQLite → PostgreSQL → MySQL), basta alterar DATABASE_URL no .env.
Nenhuma linha desta classe ou das subclasses precisa mudar.
"""
from ..extensions import db


class BaseRepository:
    def __init__(self, model):
        self.model = model
        self.session = db.session

    def get_by_id(self, id):
        return self.session.get(self.model, id)

    def get_all(self):
        return self.session.execute(
            db.select(self.model)
        ).scalars().all()

    def filter_by(self, **kwargs):
        return self.session.execute(
            db.select(self.model).filter_by(**kwargs)
        ).scalars().all()

    def filter_one(self, **kwargs):
        return self.session.execute(
            db.select(self.model).filter_by(**kwargs)
        ).scalar_one_or_none()

    def create(self, **kwargs):
        obj = self.model(**kwargs)
        self.session.add(obj)
        self.session.commit()
        return obj

    def update(self, obj, **kwargs):
        for key, value in kwargs.items():
            setattr(obj, key, value)
        self.session.commit()
        return obj

    def delete(self, obj):
        self.session.delete(obj)
        self.session.commit()

    def save(self, obj):
        self.session.add(obj)
        self.session.commit()
        return obj

    def paginate(self, page, per_page=20, query=None):
        if query is None:
            query = db.select(self.model)
        return self.session.execute(
            query.limit(per_page).offset((page - 1) * per_page)
        ).scalars().all()

    def count(self, **kwargs):
        from sqlalchemy import func
        q = db.select(func.count()).select_from(self.model)
        if kwargs:
            q = q.filter_by(**kwargs)
        return self.session.execute(q).scalar()
