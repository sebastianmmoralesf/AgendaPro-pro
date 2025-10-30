from project import db, bcrypt
from flask_login import UserMixin
from datetime import datetime, timezone, timedelta

# ✅ CONFIGURACIÓN: Zona horaria de Perú (UTC-5)
PERU_TZ = timezone(timedelta(hours=-5))

def get_peru_time():
    """Obtiene la hora actual en zona horaria de Perú (UTC-5)"""
    return datetime.now(PERU_TZ)


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    password_hash = db.Column(db.String(128), nullable=True)
    role = db.Column(db.String(20), nullable=False, default='cliente')
    google_id = db.Column(db.String(200), unique=True, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(PERU_TZ))
    is_active = db.Column(db.Boolean, default=True)
    
    appointments_as_professional = db.relationship('Appointment', 
                                                   foreign_keys='Appointment.professional_id',
                                                   backref='professional', 
                                                   lazy=True, 
                                                   cascade='all, delete-orphan')
    appointments_as_client = db.relationship('Appointment', 
                                            foreign_keys='Appointment.client_id',
                                            backref='client', 
                                            lazy=True)
    
    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')
    
    def check_password(self, password):
        if not self.password_hash:
            return False
        return bcrypt.check_password_hash(self.password_hash, password)
    
    def is_admin(self):
        return self.role == 'admin'
    
    def is_professional(self):
        return self.role in ['admin', 'profesional']
    
    def is_client(self):
        return self.role == 'cliente'


class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_name = db.Column(db.String(100), nullable=False)
    start_datetime = db.Column(db.DateTime, nullable=False)
    end_datetime = db.Column(db.DateTime, nullable=False)
    
    # ✅ MEJORADO: Estados claros y validados
    # Valores permitidos: 'programada', 'completada', 'cancelada'
    status = db.Column(db.String(50), nullable=False, default='programada')
    
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(PERU_TZ))
    
    # ✅ NUEVO: Campo para rastrear cuándo se canceló
    cancelled_at = db.Column(db.DateTime, nullable=True)
    cancellation_reason = db.Column(db.String(200), nullable=True)
    
    professional_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    
    def to_dict(self, include_timezone_offset=False):
        """
        Convierte el appointment a diccionario para JSON.
        
        Args:
            include_timezone_offset: Si True, incluye la zona horaria en el ISO string
        """
        # ✅ FIX: Convertir datetime naive a aware con timezone de Perú
        start_aware = self.start_datetime.replace(tzinfo=PERU_TZ) if self.start_datetime.tzinfo is None else self.start_datetime
        end_aware = self.end_datetime.replace(tzinfo=PERU_TZ) if self.end_datetime.tzinfo is None else self.end_datetime
        
        return {
            'id': self.id,
            'patient_name': self.patient_name,
            'start_datetime': start_aware.isoformat(),
            'end_datetime': end_aware.isoformat(),
            'status': self.status,
            'notes': self.notes,
            'professional_id': self.professional_id,
            'client_id': self.client_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'cancelled_at': self.cancelled_at.isoformat() if self.cancelled_at else None,
            'cancellation_reason': self.cancellation_reason
        }
    
    def can_be_completed(self):
        """
        Verifica si una cita puede marcarse como completada.
        Solo si la fecha/hora ya pasó.
        """
        now_peru = get_peru_time()
        # Hacer aware el datetime si es naive
        end_aware = self.end_datetime.replace(tzinfo=PERU_TZ) if self.end_datetime.tzinfo is None else self.end_datetime
        return end_aware <= now_peru
    
    def can_be_cancelled(self):
        """
        Verifica si una cita puede cancelarse.
        No se puede cancelar si ya está completada o cancelada.
        """
        return self.status not in ['completada', 'cancelada']
    
    def cancel(self, reason=None):
        """
        Cancela la cita y registra la información.
        
        Args:
            reason (str): Motivo opcional de la cancelación
        """
        if not self.can_be_cancelled():
            raise ValueError(f'No se puede cancelar una cita con estado "{self.status}"')
        
        self.status = 'cancelada'
        self.cancelled_at = get_peru_time()
        self.cancellation_reason = reason or 'Sin motivo especificado'
    
    def complete(self):
        """
        Marca la cita como completada.
        Solo si ya pasó la fecha/hora.
        """
        if not self.can_be_completed():
            raise ValueError('No se puede completar una cita que aún no ha ocurrido')
        
        if self.status == 'cancelada':
            raise ValueError('No se puede completar una cita cancelada')
        
        self.status = 'completada'
    
    def overlaps_with(self, start, end, exclude_id=None):
        """
        Verifica si esta cita se solapa con un rango de fechas dado.
        ✅ MEJORADO: Solo verifica citas NO canceladas
        """
        query = Appointment.query.filter(
            Appointment.professional_id == self.professional_id,
            Appointment.status != 'cancelada',  # ✅ Ignorar canceladas
            Appointment.start_datetime < end,
            Appointment.end_datetime > start
        )
        
        if exclude_id:
            query = query.filter(Appointment.id != exclude_id)
        
        return query.first() is not None


class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message = db.Column(db.String(200), nullable=False)
    type = db.Column(db.String(20), default='info')
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(PERU_TZ))
    
    user = db.relationship('User', backref=db.backref('notifications', lazy=True))
