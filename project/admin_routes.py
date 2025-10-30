from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from functools import wraps
from project import db
from project.models import User, Appointment

admin_bp = Blueprint('admin', __name__)

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            flash('Acceso denegado. Se requieren permisos de administrador.', 'danger')
            return redirect(url_for('auth.dashboard'))
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route('/panel')
@login_required
@admin_required
def panel():
    users = User.query.all()
    return render_template('admin_panel.html', users=users)

@admin_bp.route('/users', methods=['GET'])
@login_required
@admin_required
def get_users():
    users = User.query.all()
    return jsonify([{
        'id': u.id,
        'username': u.username,
        'email': u.email,
        'role': u.role,
        'is_active': u.is_active,
        'created_at': u.created_at.strftime('%Y-%m-%d'),
        'appointments_count': len(u.appointments_as_professional)
    } for u in users])

@admin_bp.route('/users/<int:id>/toggle-active', methods=['POST'])
@login_required
@admin_required
def toggle_user_active(id):
    user = User.query.get_or_404(id)
    
    if user.id == current_user.id:
        return jsonify({'error': 'No puedes desactivar tu propia cuenta'}), 400
    
    user.is_active = not user.is_active
    db.session.commit()
    
    status = 'activado' if user.is_active else 'desactivado'
    return jsonify({'message': f'Usuario {status} exitosamente', 'is_active': user.is_active})

@admin_bp.route('/users/<int:id>/change-role', methods=['POST'])
@login_required
@admin_required
def change_user_role(id):
    user = User.query.get_or_404(id)
    data = request.get_json()
    new_role = data.get('role')
    
    if new_role not in ['admin', 'profesional', 'cliente']:
        return jsonify({'error': 'Rol inválido'}), 400
    
    if user.id == current_user.id and new_role != 'admin':
        return jsonify({'error': 'No puedes cambiar tu propio rol de admin'}), 400
    
    user.role = new_role
    db.session.commit()
    
    return jsonify({'message': f'Rol actualizado a {new_role}'})
