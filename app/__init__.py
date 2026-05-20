import os

from flask import Flask
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = "main.login"
login_manager.login_message_category = "info"


def create_app():
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
    )
    app.config["SECRET_KEY"] = os.environ.get(
        "SECRET_KEY",
        "dev-only-change-this-secret-key",
    )
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
        "DATABASE_URL",
        "sqlite:///medical_inventory.db",
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)
    login_manager.init_app(app)

    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    from app.main_routes import main_bp
    from app.admin_routes import admin_bp
    from app.staff_routes import staff_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(staff_bp, url_prefix="/staff")

    from datetime import date, datetime

    from app.utils import paginate_url

    @app.context_processor
    def inject_globals():
        return {
            "today": date.today(),
            "moment": datetime.now().strftime("%A, %d %B %Y · %H:%M"),
        }

    @app.template_global()
    def paginate_url_global(page: int):
        try:
            p = int(page)
        except (TypeError, ValueError):
            p = 1
        return paginate_url(p)

    with app.app_context():
        db.create_all()
        _ensure_default_admin(app)

    return app


def _ensure_default_admin(app):
    from app.models import User
    from werkzeug.security import generate_password_hash

    if User.query.filter_by(username="admin").first():
        return
    admin = User(
        username="admin",
        password_hash=generate_password_hash("admin123"),
        full_name="System Administrator",
        email="admin@medinventory.local",
        phone="0000000000",
        role="admin",
        is_active=True,
    )
    db.session.add(admin)
    db.session.commit()
