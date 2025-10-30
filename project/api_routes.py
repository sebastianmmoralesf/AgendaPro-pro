from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from project import db
from project.models import Appointment, Notification, User, PERU_TZ, get_peru_time
from datetime import datetime

api_bp = Blueprint('api', __name__)


def parse_datetime(date_string):
    """
    Parsea una fecha ISO 8601 y la convierte a zona horaria de Perú.
    ✅ FIX: Maneja correctamente la zona horaria para evitar desfases
    """
    try:
        # Parsear el string ISO
        dt = datetime.fromisoformat(date_string.replace('Z', '+00:00'))
        
        # Si tiene timezone, convertir a Perú. Si no, asumir que es hora local de Perú
        if dt.tzinfo is not None:
            # Convertir a hora de Perú
            dt_peru = dt.astimezone(PERU_TZ)
        else:
            # Es hora naive, asumimos que ya es hora de Perú
            dt_peru = dt.replace(tzinfo=PERU_TZ)
        
        # Retornar como naive (sin timezone) para SQLite
        return dt_peru.replace(tzinfo=None)
        
    except (ValueError, AttributeError) as e:
        # Fallback: intentar formatos sin timezone
        try:
            dt = datetime.strptime(date_string, '%Y-%m-%dT%H:%M:%S')
            return dt
        except ValueError:
            dt = datetime.strptime(date_string, '%Y-%m-%dT%H:%M')
            return dt


def check_appointment_overlap(professional_id, start_dt, end_dt, exclude_appointment_id=None):
    """
    Verifica solapamiento excluyendo citas canceladas.
    """
    query = Appointment.query.filter(
        Appointment.professional_id == professional_id,
        Appointment.status != 'cancelada',  # ✅ Ignorar canceladas
        Appointment.start_datetime < end_dt,
        Appointment.end_datetime > start_dt
    )
    
    if exclude_appointment_id:
        query = query.filter(Appointment.id != exclude_appointment_id)
    
    return query.first()


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


@api_bp.route('/appointments', methods=['GET'])
@login_required
def get_appointments():
    """
    ✅ MEJORADO: Solo retorna citas programadas y completadas para el calendario
    Las canceladas se obtienen por endpoint separado
    """
    if current_user.is_admin():
        appointments = Appointment.query.filter(
            Appointment.status.in_(['programada', 'completada'])
        ).all()
    elif current_user.is_professional():
        appointments = Appointment.query.filter_by(
            professional_id=current_user.id
        ).filter(
            Appointment.status.in_(['programada', 'completada'])
        ).all()
    else:
        appointments = Appointment.query.filter_by(
            client_id=current_user.id
        ).filter(
            Appointment.status.in_(['programada', 'completada'])
        ).all()
    
    events = []
    for apt in appointments:
        # Color por estado
        if apt.status == 'completada':
            color = '#198754'  # Verde
        else:  # programada
            color = '#0d6efd'  # Azul
        
        # ✅ FIX: Timezone aware para evitar desfase
        start_aware = apt.start_datetime.replace(tzinfo=PERU_TZ) if apt.start_datetime.tzinfo is None else apt.start_datetime
        end_aware = apt.end_datetime.replace(tzinfo=PERU_TZ) if apt.end_datetime.tzinfo is None else apt.end_datetime
        
        events.append({
            'id': apt.id,
            'title': apt.patient_name,
            'start': start_aware.isoformat(),
            'end': end_aware.isoformat(),
            'backgroundColor': color,
            'borderColor': color,
            'extendedProps': {
                'patient_name': apt.patient_name,
                'status': apt.status,
                'notes': apt.notes or '',
                'professional': apt.professional.username if apt.professional else 'N/A',
                'client': apt.client.username if apt.client else 'N/A',
                'client_id': apt.client_id,
                'can_complete': apt.can_be_completed(),
                'can_cancel': apt.can_be_cancelled()
            }
        })
    
    return jsonify(events)


@api_bp.route('/appointments/cancelled', methods=['GET'])
@login_required
def get_cancelled_appointments():
    """
    ✅ NUEVO: Endpoint para obtener citas canceladas (historial)
    """
    if current_user.is_admin():
        appointments = Appointment.query.filter_by(status='cancelada').order_by(Appointment.cancelled_at.desc()).all()
    elif current_user.is_professional():
        appointments = Appointment.query.filter_by(
            professional_id=current_user.id,
            status='cancelada'
        ).order_by(Appointment.cancelled_at.desc()).all()
    else:
        appointments = Appointment.query.filter_by(
            client_id=current_user.id,
            status='cancelada'
        ).order_by(Appointment.cancelled_at.desc()).all()
    
    return jsonify([
        {
            'id': apt.id,
            'patient_name': apt.patient_name,
            'start_datetime': apt.start_datetime.isoformat(),
            'end_datetime': apt.end_datetime.isoformat(),
            'professional': apt.professional.username if apt.professional else 'N/A',
            'client': apt.client.username if apt.client else 'Sin asignar',
            'cancelled_at': apt.cancelled_at.isoformat() if apt.cancelled_at else None,
            'cancellation_reason': apt.cancellation_reason or 'Sin motivo especificado',
            'notes': apt.notes or ''
        }
        for apt in appointments
    ])


@api_bp.route('/appointments', methods=['POST'])
@login_required
def create_appointment():
    if not current_user.is_professional():
        return jsonify({'error': 'Solo profesionales pueden crear citas'}), 403
    
    data = request.get_json()
    
    if not all(k in data for k in ['patient_name', 'start_datetime', 'end_datetime']):
        return jsonify({'error': 'Faltan campos requeridos'}), 400
    
    try:
        start_dt = parse_datetime(data['start_datetime'])
        end_dt = parse_datetime(data['end_datetime'])
    except (ValueError, KeyError) as e:
        return jsonify({'error': f'Formato de fecha inválido: {str(e)}'}), 400
    
    if end_dt <= start_dt:
        return jsonify({'error': 'La fecha de fin debe ser posterior a la fecha de inicio'}), 400
    
    # Verificar solapamiento
    overlapping = check_appointment_overlap(current_user.id, start_dt, end_dt)
    if overlapping:
        return jsonify({
            'error': 'La cita se solapa con otra existente',
            'conflicting_appointment': {
                'id': overlapping.id,
                'patient': overlapping.patient_name,
                'start': overlapping.start_datetime.isoformat(),
                'end': overlapping.end_datetime.isoformat()
            }
        }), 400
    
    appointment = Appointment(
        patient_name=data.get('patient_name'),
        start_datetime=start_dt,
        end_datetime=end_dt,
        status='programada',  # ✅ Siempre inicia como programada
        notes=data.get('notes', ''),
        professional_id=current_user.id,
        client_id=data.get('client_id')
    )
    
    db.session.add(appointment)

    if appointment.client_id:
        notif = Notification(
            user_id=appointment.client_id,
            message=f'Nueva cita: {appointment.patient_name} el {start_dt.strftime("%d/%m/%Y %H:%M")}',
            type='info'
        )
        db.session.add(notif)
    
    db.session.commit()
    
    return jsonify({
        'message': 'Cita creada exitosamente',
        'id': appointment.id,
        'appointment': appointment.to_dict()
    }), 201


@api_bp.route('/appointments/<int:id>', methods=['PUT'])
@login_required
def update_appointment(id):
    """
    ✅ MEJORADO: Solo permite actualizar datos básicos, NO el estado
    El estado se cambia por endpoints dedicados
    """
    appointment = Appointment.query.get_or_404(id)
    
    if not current_user.is_admin() and appointment.professional_id != current_user.id:
        return jsonify({'error': 'No autorizado'}), 403
    
    data = request.get_json()
    
    start_dt = appointment.start_datetime
    end_dt = appointment.end_datetime
    
    if 'start_datetime' in data:
        try:
            start_dt = parse_datetime(data['start_datetime'])
        except ValueError as e:
            return jsonify({'error': f'Formato de fecha inicio inválido: {str(e)}'}), 400
    
    if 'end_datetime' in data:
        try:
            end_dt = parse_datetime(data['end_datetime'])
        except ValueError as e:
            return jsonify({'error': f'Formato de fecha fin inválido: {str(e)}'}), 400
    
    if end_dt <= start_dt:
        return jsonify({'error': 'La fecha de fin debe ser posterior a la fecha de inicio'}), 400
    
    # Verificar solapamiento si cambiaron las fechas
    if 'start_datetime' in data or 'end_datetime' in data:
        overlapping = check_appointment_overlap(
            appointment.professional_id,
            start_dt,
            end_dt,
            exclude_appointment_id=id
        )
        
        if overlapping:
            return jsonify({
                'error': 'La cita se solapa con otra existente',
                'conflicting_appointment': {
                    'id': overlapping.id,
                    'patient': overlapping.patient_name,
                    'start': overlapping.start_datetime.isoformat(),
                    'end': overlapping.end_datetime.isoformat()
                }
            }), 400
    
    # Actualizar campos permitidos
    appointment.patient_name = data.get('patient_name', appointment.patient_name)
    appointment.start_datetime = start_dt
    appointment.end_datetime = end_dt
    appointment.notes = data.get('notes', appointment.notes)
    
    if 'client_id' in data:
        old_client_id = appointment.client_id
        appointment.client_id = data.get('client_id')
        
        if appointment.client_id and appointment.client_id != old_client_id:
            notif = Notification(
                user_id=appointment.client_id,
                message=f'Cita asignada: {appointment.patient_name} el {start_dt.strftime("%d/%m/%Y %H:%M")}',
                type='info'
            )
            db.session.add(notif)
    
    if appointment.client_id:
        notif = Notification(
            user_id=appointment.client_id,
            message=f'Cita actualizada: {appointment.patient_name} el {start_dt.strftime("%d/%m/%Y %H:%M")}',
            type='warning'
        )
        db.session.add(notif)
    
    db.session.commit()
    return jsonify({
        'message': 'Cita actualizada exitosamente',
        'appointment': appointment.to_dict()
    })


@api_bp.route('/appointments/<int:id>/complete', methods=['POST'])
@login_required
def complete_appointment(id):
    """
    ✅ NUEVO: Endpoint dedicado para completar citas
    """
    appointment = Appointment.query.get_or_404(id)
    
    if not current_user.is_professional():
        return jsonify({'error': 'Solo profesionales pueden completar citas'}), 403
    
    if not current_user.is_admin() and appointment.professional_id != current_user.id:
        return jsonify({'error': 'No autorizado'}), 403
    
    try:
        appointment.complete()
        
        if appointment.client_id:
            notif = Notification(
                user_id=appointment.client_id,
                message=f'Cita completada: {appointment.patient_name}',
                type='success'
            )
            db.session.add(notif)
        
        db.session.commit()
        return jsonify({
            'message': 'Cita marcada como completada',
            'appointment': appointment.to_dict()
        })
    except ValueError as e:
        return jsonify({'error': str(e)}), 400


@api_bp.route('/appointments/<int:id>/cancel', methods=['POST'])
@login_required
def cancel_appointment(id):
    """
    ✅ NUEVO: Endpoint dedicado para cancelar citas
    """
    appointment = Appointment.query.get_or_404(id)
    
    if not current_user.is_professional():
        return jsonify({'error': 'Solo profesionales pueden cancelar citas'}), 403
    
    if not current_user.is_admin() and appointment.professional_id != current_user.id:
        return jsonify({'error': 'No autorizado'}), 403
    
    data = request.get_json() or {}
    reason = data.get('reason', 'Cancelado por el profesional')
    
    try:
        appointment.cancel(reason)
        
        if appointment.client_id:
            notif = Notification(
                user_id=appointment.client_id,
                message=f'Cita cancelada: {appointment.patient_name}. Motivo: {reason}',
                type='danger'
            )
            db.session.add(notif)
        
        db.session.commit()
        return jsonify({
            'message': 'Cita cancelada exitosamente',
            'appointment': appointment.to_dict()
        })
    except ValueError as e:
        return jsonify({'error': str(e)}), 400


@api_bp.route('/appointments/<int:id>', methods=['DELETE'])
@login_required
def delete_appointment(id):
    """
    ✅ NOTA: Este endpoint ahora solo elimina permanentemente
    Para cancelar, usar /appointments/:id/cancel
    """
    appointment = Appointment.query.get_or_404(id)
    
    # Solo admin puede eliminar permanentemente
    if not current_user.is_admin():
        return jsonify({'error': 'Solo administradores pueden eliminar citas permanentemente'}), 403
    
    if appointment.client_id:
        notif = Notification(
            user_id=appointment.client_id,
            message=f'Cita eliminada: {appointment.patient_name}',
            type='danger'
        )
        db.session.add(notif)
    
    db.session.delete(appointment)
    db.session.commit()
    return jsonify({'message': 'Cita eliminada permanentemente'})


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


@api_bp.route('/notifications/<int:id>/read', methods=['POST'])
@login_required
def mark_notification_read(id):
    notification = Notification.query.get_or_404(id)
    
    if notification.user_id != current_user.id:
        return jsonify({'error': 'No autorizado'}), 403
    
    notification.is_read = True
    db.session.commit()
    return jsonify({'message': 'Notificación marcada como leída'})


@api_bp.route('/stats', methods=['GET'])
@login_required
def get_stats():
    stats = {}
    
    if current_user.is_admin():
        stats['total_users'] = User.query.count()
        stats['total_appointments'] = Appointment.query.filter(
            Appointment.status != 'cancelada'
        ).count()
        stats['active_appointments'] = Appointment.query.filter_by(status='programada').count()
        stats['cancelled_appointments'] = Appointment.query.filter_by(status='cancelada').count()
    elif current_user.is_professional():
        stats['my_appointments'] = Appointment.query.filter_by(
            professional_id=current_user.id
        ).filter(Appointment.status != 'cancelada').count()
        stats['pending'] = Appointment.query.filter_by(
            professional_id=current_user.id, status='programada'
        ).count()
        stats['completed'] = Appointment.query.filter_by(
            professional_id=current_user.id, status='completada'
        ).count()
        stats['cancelled'] = Appointment.query.filter_by(
            professional_id=current_user.id, status='cancelada'
        ).count()
    else:
        stats['my_appointments'] = Appointment.query.filter_by(
            client_id=current_user.id
        ).filter(Appointment.status != 'cancelada').count()
        stats['upcoming'] = Appointment.query.filter_by(
            client_id=current_user.id, status='programada'
        ).count()
    
    return jsonify(stats)

