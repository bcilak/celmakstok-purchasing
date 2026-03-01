from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from config import Config

db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Extensions
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Lütfen giriş yapın.'
    
    # Blueprints
    from app.routes import auth, main, purchasing, suppliers, admin
    
    app.register_blueprint(auth.auth_bp)
    app.register_blueprint(main.main_bp)
    app.register_blueprint(purchasing.purchasing_bp, url_prefix='/purchasing')
    app.register_blueprint(suppliers.suppliers_bp, url_prefix='/suppliers')
    app.register_blueprint(admin.admin_bp)
    
    return app
