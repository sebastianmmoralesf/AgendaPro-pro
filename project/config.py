import os

class Config:
    # Secret Key
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    
    # Database
    # En Render, usar SQLite dentro de /opt/render/project/src/instance
    # Para mayor escalabilidad, considera PostgreSQL
    DATABASE_PATH = os.environ.get('DATABASE_PATH', '/tmp/database.db')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or f'sqlite:///{DATABASE_PATH}'
    
    # Si usas PostgreSQL en Render
    if SQLALCHEMY_DATABASE_URI and SQLALCHEMY_DATABASE_URI.startswith("postgres://"):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace("postgres://", "postgresql://", 1)
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Google OAuth Configuration
    GOOGLE_OAUTH_CLIENT_ID = os.environ.get('GOOGLE_OAUTH_CLIENT_ID')
    GOOGLE_OAUTH_CLIENT_SECRET = os.environ.get('GOOGLE_OAUTH_CLIENT_SECRET')
    OAUTHLIB_INSECURE_TRANSPORT = os.environ.get('OAUTHLIB_INSECURE_TRANSPORT', '0')
    OAUTHLIB_RELAX_TOKEN_SCOPE = '1'
    
    # Flask Environment
    FLASK_ENV = os.environ.get('FLASK_ENV', 'production')
    DEBUG = os.environ.get('FLASK_ENV') != 'production'

