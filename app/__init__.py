from datetime import date

from flask import Flask
from flask_login import current_user

from app.extensions import db, login_manager
from config import Config


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    login_manager.init_app(app)

    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    @app.context_processor
    def inject_globals():
        from app.permissions import user_has_permission

        def user_can(module, action="view"):
            return user_has_permission(current_user, module, action)

        return {"user_can": user_can}

    from app.routes.auth import auth_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.entries import entries_bp
    from app.routes.masters import masters_bp
    from app.routes.reports import reports_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(masters_bp, url_prefix="/masters")
    app.register_blueprint(entries_bp, url_prefix="/entries")
    app.register_blueprint(reports_bp, url_prefix="/reports")

    with app.app_context():
        db.create_all()
        from app.migrate import _migrate_db

        _migrate_db()
        _ensure_default_admin()

    return app


def _ensure_default_admin():
    from app.models import User

    if not User.query.filter_by(username="admin").first():
        admin = User(username="admin", role="admin")
        admin.set_password("admin123")
        db.session.add(admin)
        db.session.commit()
