from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from flask_dance.contrib.google import google
from project import db
from project.models import User, Notification

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/')
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('auth.dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            if not user.is_active:
                flash('Tu cuenta ha sido desactivada. Contacta al administrador.', 'danger')
                return redirect(url_for('auth.login'))
            
            login_user(user, remember=True)
            
            # Crear notificación de bienvenida
            welcome_msg = Notification(
                user_id=user.id,
                message=f'¡Bienvenido de nuevo, {user.username}!',
                type='success'
            )
            db.session.add(welcome_msg)
            db.session.commit()
            
            flash(f'¡Bienvenido, {user.username}!', 'success')
            
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('auth.dashboard'))
        else:
            flash('Credenciales inválidas. Verifica tu usuario y contraseña.', 'danger')
    
    return render_template('login.html')

@auth_bp.route('/google-login')
def google_login():
    # Verificar si Google OAuth está configurado
    try:
        if not google.authorized:
            return redirect(url_for('google.login'))
        
        resp = google.get('/oauth2/v2/userinfo')
        if not resp.ok:
            flash('Error al obtener información de Google.', 'danger')
            return redirect(url_for('auth.login'))
        
        google_info = resp.json()
        google_id = google_info['id']
        email = google_info['email']
        name = google_info.get('name', email.split('@')[0])
        
        # Buscar usuario existente
        user = User.query.filter_by(google_id=google_id).first()
        
        if not user:
            user = User.query.filter_by(email=email).first()
            if not user:
                # Crear nuevo usuario
                user = User(
                    username=name.lower().replace(' ', '_'),
                    email=email,
                    google_id=google_id,
                    role='cliente'
                )
                db.session.add(user)
                db.session.commit()
                flash('¡Cuenta creada exitosamente!', 'success')
            else:
                user.google_id = google_id
                db.session.commit()
        
        if not user.is_active:
            flash('Tu cuenta ha sido desactivada.', 'danger')
            return redirect(url_for('auth.login'))
        
        login_user(user, remember=True)
        flash(f'¡Bienvenido, {user.username}!', 'success')
        return redirect(url_for('auth.dashboard'))
        
    except Exception as e:
        flash('Google OAuth no está configurado. Por favor usa registro tradicional.', 'warning')
        return redirect(url_for('auth.register'))

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('auth.dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if password != confirm_password:
            flash('Las contraseñas no coinciden.', 'danger')
            return redirect(url_for('auth.register'))
        
        if User.query.filter_by(username=username).first():
            flash('El nombre de usuario ya está en uso.', 'danger')
            return redirect(url_for('auth.register'))
        
        if User.query.filter_by(email=email).first():
            flash('El correo electrónico ya está registrado.', 'danger')
            return redirect(url_for('auth.register'))
        
        new_user = User(
            username=username,
            email=email,
            role='cliente'
        )
        new_user.set_password(password)
        
        db.session.add(new_user)
        db.session.commit()
        
        flash('¡Registro exitoso! Ahora puedes iniciar sesión.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('register.html')

@auth_bp.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', user=current_user)

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Has cerrado sesión exitosamente.', 'info')
    return redirect(url_for('auth.login'))