import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get("SKSS_SECRET_KEY", "skss-mis-change-in-production")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'skss_mis.db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
