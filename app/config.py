import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = True
    RATELIMIT_DEFAULT = "200 per day;50 per hour"

    # Regras de negócio configuráveis
    MIN_PASSING_GRADE = 5.0      # nota mínima para aprovação
    MAX_ABSENCE_PERCENT = 25.0   # % máxima de faltas antes do alerta


class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///agenda_escolar.db"
    )
    SQLALCHEMY_ECHO = False


class ProductionConfig(Config):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")
    # Para PostgreSQL: instalar psycopg2-binary e definir DATABASE_URL=postgresql://...
    # Para MySQL: instalar mysqlclient e definir DATABASE_URL=mysql://...
    # Nenhuma outra mudança no código é necessária.


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False


config_map = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}


def get_config():
    env = os.environ.get("FLASK_ENV", "development")
    return config_map.get(env, DevelopmentConfig)
