from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from project import db
from project.models import Appointment, Notification, User
from datetime import datetime

# --- Definir Blueprint ---
api_bp = Blueprint('api', __name__)

# --- RUTA: Obtener clientes (solo profesionales) ---
@api_bp.route('/clients', methods=['GET'])
@login_required
def get_clients():
    if not current_user.is_professional():
        return jsonify({'error': 'No autorizado'}), 403
    
    clients = User.query.filter_by(role='cliente', is_active=True).all()
    return jsonify([
        {'id': c.id, 'username': c.username, 'email': c.email}
        for c in clients
    ])


# --- RUTA: Obtener citas según rol ---
@api_bp.route('/appointments', methods=['GET'])
@login_required
def get_appointments():
    if current_user.is_admin():
        appointments = Appointment.query.all()
    elif current_user.is_professional():
        appointments = Appointment.query.filter_by(professional_id=current_user.id).all()
    else:
        appointments = Appointment.query.filter_by(client_id=current_user.id).all()
    
    events = []
    for apt in appointments:
        color = '#0d6efd'
        if apt.status == 'Completada':
            color = '#198754'
        elif apt.status == 'Cancelada':
            color = '#dc3545'
        
        events.append({
            'id': apt.id,
            'title': apt.patient_name,
            'start': apt.start_datetime,
            'end': apt.end_datetime,
            'backgroundColor': color,
            'borderColor': color,
            'extendedProps': {
                'patient_name': apt.patient_name,
                'status': apt.status,
                'notes': apt.notes,
                'professional': apt.professional.username if apt.professional else 'N/A',
                'client': apt.client.username if apt.client else 'N/A',
                'client_id': apt.client_id  # ✅ NUEVO: Agregado client_id
            }
        })
    
    return jsonify(events)


# --- RUTA: Crear cita (solo profesionales) ---
@api_bp.route('/appointments', methods=['POST'])
@login_required
def create_appointment():
    if not current_user.is_professional():
        return jsonify({'error': 'Solo profesionales pueden crear citas'}), 403
    
    data = request.get_json()
    
    appointment = Appointment(
        patient_name=data.get('patient_name'),
        start_datetime=data.get('start_datetime'),
        end_datetime=data.get('end_datetime'),
        status=data.get('status', 'Programada'),
        notes=data.get('notes', ''),
        professional_id=current_user.id,
        client_id=data.get('client_id')  # ✅ Esto ya estaba bien
    )
    
    db.session.add(appointment)

    # Crear notificación para cliente
    if appointment.client_id:
        notif = Notification(
            user_id=appointment.client_id,
            message=f'Nueva cita programada: {appointment.patient_name}',
            type='info'
        )
        db.session.add(notif)
    
    db.session.commit()
    return jsonify({'message': 'Cita creada exitosamente', 'id': appointment.id}), 201


# --- RUTA: Actualizar cita ---
@api_bp.route('/appointments/<int:id>', methods=['PUT'])
@login_required
def update_appointment(id):
    appointment = Appointment.query.get_or_404(id)
    
    if not current_user.is_admin() and appointment.professional_id != current_user.id:
        return jsonify({'error': 'No autorizado'}), 403
    
    data = request.get_json()
    appointment.patient_name = data.get('patient_name', appointment.patient_name)
    appointment.start_datetime = data.get('start_datetime', appointment.start_datetime)
    appointment.end_datetime = data.get('end_datetime', appointment.end_datetime)
    appointment.status = data.get('status', appointment.status)
    appointment.notes = data.get('notes', appointment.notes)
    
    # ✅ NUEVO: Actualizar client_id si viene en el request
    if 'client_id' in data:
        appointment.client_id = data.get('client_id')
    
    if appointment.client_id:
        notif = Notification(
            user_id=appointment.client_id,
            message=f'Cita actualizada: {appointment.patient_name}',
            type='warning'
        )
        db.session.add(notif)
    
    db.session.commit()
    return jsonify({'message': 'Cita actualizada exitosamente'})


# --- RUTA: Eliminar cita ---
@api_bp.route('/appointments/<int:id>', methods=['DELETE'])
@login_required
def delete_appointment(id):
    appointment = Appointment.query.get_or_404(id)
    
    if not current_user.is_admin() and appointment.professional_id != current_user.id:
        return jsonify({'error': 'No autorizado'}), 403
    
    if appointment.client_id:
        notif = Notification(
            user_id=appointment.client_id,
            message=f'Cita cancelada: {appointment.patient_name}',
            type='danger'
        )
        db.session.add(notif)
    
    db.session.delete(appointment)
    db.session.commit()
    return jsonify({'message': 'Cita eliminada exitosamente'})


# --- RUTA: Obtener notificaciones ---
@api_bp.route('/notifications', methods=['GET'])
@login_required
def get_notifications():
    notifications = Notification.query.filter_by(
        user_id=current_user.id, 
        is_read=False
    ).order_by(Notification.created_at.desc()).limit(10).all()
    
    return jsonify([
        {
            'id': n.id,
            'message': n.message,
            'type': n.type,
            'created_at': n.created_at.strftime('%Y-%m-%d %H:%M')
        } for n in notifications
    ])


# --- RUTA: Marcar notificación como leída ---
@api_bp.route('/notifications/<int:id>/read', methods=['POST'])
@login_required
def mark_notification_read(id):
    notification = Notification.query.get_or_404(id)
    
    if notification.user_id != current_user.id:
        return jsonify({'error': 'No autorizado'}), 403
    
    notification.is_read = True
    db.session.commit()
    return jsonify({'message': 'Notificación marcada como leída'})


# --- RUTA: Estadísticas por rol ---
@api_bp.route('/stats', methods=['GET'])
@login_required
def get_stats():
    stats = {}
    
    if current_user.is_admin():
        stats['total_users'] = User.query.count()
        stats['total_appointments'] = Appointment.query.count()
        stats['active_appointments'] = Appointment.query.filter_by(status='Programada').count()
    elif current_user.is_professional():
        stats['my_appointments'] = Appointment.query.filter_by(professional_id=current_user.id).count()
        stats['pending'] = Appointment.query.filter_by(
            professional_id=current_user.id, status='Programada'
        ).count()
        stats['completed'] = Appointment.query.filter_by(
            professional_id=current_user.id, status='Completada'
        ).count()
    else:
        stats['my_appointments'] = Appointment.query.filter_by(client_id=current_user.id).count()
        stats['upcoming'] = Appointment.query.filter_by(
            client_id=current_user.id, status='Programada'
        ).count()
    
    return jsonify(stats)
