from flask import Flask
from .extensions import db
from flask_migrate import Migrate
import os

def create_app():
    flask_app = Flask(__name__)
    flask_app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/postgres')
    flask_app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    flask_app.config['SECRET_KEY'] = 'dev'

    db.init_app(flask_app)

    with flask_app.app_context():
        import app.models

    from app.routes.main import main_bp
    from app.routes.student import student_bp
    from app.routes.admin import admin_bp
    from app.routes.api import api_bp
    from app.routes.recovery import recovery_bp
    from app.routes.system_admin import system_admin_bp
    from app.routes.analytics import analytics_bp
    from app.routes.docs import docs_bp

    flask_app.register_blueprint(main_bp)
    flask_app.register_blueprint(student_bp)
    flask_app.register_blueprint(admin_bp)
    flask_app.register_blueprint(api_bp)
    flask_app.register_blueprint(recovery_bp)
    flask_app.register_blueprint(system_admin_bp)
    flask_app.register_blueprint(analytics_bp)
    flask_app.register_blueprint(docs_bp)

    return flask_app
