from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager
from flask_cors import CORS
from flask_dance.contrib.google import make_google_blueprint

db = SQLAlchemy()
bcrypt = Bcrypt()
login_manager = LoginManager()

def create_app():
    app = Flask(__name__)
    app.config.from_object('project.config.Config')
    
    db.init_app(app)
    bcrypt.init_app(app)
    login_manager.init_app(app)
    CORS(app)
    
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Por favor inicia sesión para acceder a esta página.'
    login_manager.login_message_category = 'warning'
    
    # Google OAuth Blueprint
    if app.config.get('GOOGLE_OAUTH_CLIENT_ID'):
        google_bp = make_google_blueprint(
            client_id=app.config['GOOGLE_OAUTH_CLIENT_ID'],
            client_secret=app.config['GOOGLE_OAUTH_CLIENT_SECRET'],
            scope=["openid", "https://www.googleapis.com/auth/userinfo.email", 
                   "https://www.googleapis.com/auth/userinfo.profile"],
            redirect_to='auth.google_login'
        )
        app.register_blueprint(google_bp, url_prefix="/login")
    
    from project.models import User
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    from project.auth_routes import auth_bp
    from project.api_routes import api_bp
    from project.admin_routes import admin_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    
    with app.app_context():
        db.create_all()
        
        # Crear usuario admin si no existe
        if not User.query.filter_by(username='admin').first():
            admin = User(
                username='admin',
                email='admin@agendapro.com',
                role='admin'
            )
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
        
        # Crear usuario profesional de prueba
        if not User.query.filter_by(username='doctor').first():
            doctor = User(
                username='doctor',
                email='doctor@agendapro.com',
                role='profesional'
            )
            doctor.set_password('doctor123')
            db.session.add(doctor)
            db.session.commit()
        
        # Crear usuario cliente de prueba
        if not User.query.filter_by(username='cliente').first():
            cliente = User(
                username='cliente',
                email='cliente@agendapro.com',
                role='cliente'
            )
            cliente.set_password('cliente123')
            db.session.add(cliente)
            db.session.commit()
    
    return app

