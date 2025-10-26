let calendar;
let currentEventId = null;
let currentUserRole = null;

document.addEventListener('DOMContentLoaded', function() {
    initializeCalendar();
    loadStatistics();
    setupEventListeners();
    loadClients(); // ✅ Ahora implementada
});

// ✅ NUEVA FUNCIÓN: Cargar clientes para el dropdown
function loadClients() {
    // Solo cargar si es profesional o admin
    const roleBadge = document.querySelector('.role-badge');
    if (!roleBadge || (!roleBadge.classList.contains('profesional') && !roleBadge.classList.contains('admin'))) {
        return;
    }
    
    fetch('/api/clients')
        .then(response => {
            if (!response.ok) {
                throw new Error('No autorizado');
            }
            return response.json();
        })
        .then(clients => {
            const clientSelect = document.getElementById('client_id');
            if (clientSelect) {
                // Mantener opción vacía por defecto
                clientSelect.innerHTML = '<option value="">-- Sin asignar --</option>';
                
                clients.forEach(client => {
                    const option = document.createElement('option');
                    option.value = client.id;
                    option.textContent = `${client.username} (${client.email})`;
                    clientSelect.appendChild(option);
                });
            }
        })
        .catch(error => {
            console.error('Error loading clients:', error);
            // Si no es profesional, simplemente no hacer nada
        });
}

function initializeCalendar() {
    const calendarEl = document.getElementById('calendar-container');
    
    calendar = new FullCalendar.Calendar(calendarEl, {
        initialView: 'dayGridMonth',
        locale: 'es',
        headerToolbar: {
            left: 'prev,next today',
            center: 'title',
            right: 'dayGridMonth,timeGridWeek,timeGridDay,listWeek'
        },
        buttonText: {
            today: 'Hoy',
            month: 'Mes',
            week: 'Semana',
            day: 'Día',
            list: 'Lista'
        },
        selectable: true,
        editable: true,
        eventResizableFromStart: true,
        events: function(info, successCallback, failureCallback) {
            fetch(`/api/appointments?start=${info.startStr}&end=${info.endStr}`)
                .then(response => response.json())
                .then(data => {
                    successCallback(data);
                })
                .catch(error => {
                    console.error('Error fetching appointments:', error);
                    failureCallback(error);
                });
        },
        select: function(info) {
            // Solo profesionales y admins pueden crear citas
            const roleBadge = document.querySelector('.role-badge');
            if (roleBadge && (roleBadge.classList.contains('profesional') || roleBadge.classList.contains('admin'))) {
                currentEventId = null;
                openAppointmentModal(info.startStr, info.endStr);
            } else {
                showToast('Solo los profesionales pueden crear citas', 'warning');
            }
        },
        eventClick: function(info) {
            currentEventId = info.event.id;
            showAppointmentDetails(info.event);
        },
        eventDrop: function(info) {
            updateEventDates(info.event);
        },
        eventResize: function(info) {
            updateEventDates(info.event);
        }
    });
    
    calendar.render();
}

function openNewAppointmentModal() {
    currentEventId = null;
    const now = new Date();
    const startStr = now.toISOString().slice(0, 16);
    const endDate = new Date(now.getTime() + 60 * 60 * 1000);
    const endStr = endDate.toISOString().slice(0, 16);
    openAppointmentModal(startStr, endStr);
}

function openAppointmentModal(startStr, endStr) {
    const modal = new bootstrap.Modal(document.getElementById('appointmentModal'));
    const modalTitle = document.getElementById('modalTitle');
    const form = document.getElementById('appointmentForm');
    const deleteBtn = document.getElementById('deleteBtn');
    
    modalTitle.innerHTML = '<i class="fas fa-calendar-plus"></i> Añadir Cita';
    form.reset();
    
    document.getElementById('start_datetime').value = startStr.slice(0, 16);
    document.getElementById('end_datetime').value = endStr ? endStr.slice(0, 16) : startStr.slice(0, 16);
    
    // ✅ Resetear el select de cliente
    const clientSelect = document.getElementById('client_id');
    if (clientSelect) {
        clientSelect.value = '';
    }
    
    deleteBtn.style.display = 'none';
    modal.show();
}

// ✅ CORREGIDO: Ahora carga el client_id al editar
function showAppointmentDetails(event) {
    const modal = new bootstrap.Modal(document.getElementById('appointmentModal'));
    const modalTitle = document.getElementById('modalTitle');
    const deleteBtn = document.getElementById('deleteBtn');
    
    modalTitle.innerHTML = '<i class="fas fa-calendar-edit"></i> Editar Cita';
    
    document.getElementById('patient_name').value = event.extendedProps.patient_name;
    document.getElementById('start_datetime').value = event.startStr.slice(0, 16);
    document.getElementById('end_datetime').value = event.endStr ? event.endStr.slice(0, 16) : event.startStr.slice(0, 16);
    document.getElementById('status').value = event.extendedProps.status;
    document.getElementById('notes').value = event.extendedProps.notes || '';
    
    // ✅ NUEVO: Cargar client_id si existe
    const clientSelect = document.getElementById('client_id');
    if (clientSelect && event.extendedProps.client_id) {
        clientSelect.value = event.extendedProps.client_id;
    } else if (clientSelect) {
        clientSelect.value = '';
    }
    
    deleteBtn.style.display = 'inline-block';
    modal.show();
}

// ✅ CORREGIDO: Ahora envía el client_id
function saveAppointment() {
    const formData = {
        patient_name: document.getElementById('patient_name').value,
        start_datetime: document.getElementById('start_datetime').value,
        end_datetime: document.getElementById('end_datetime').value,
        status: document.getElementById('status').value,
        notes: document.getElementById('notes').value
    };
    
    // ✅ NUEVO: Agregar client_id si existe y tiene valor
    const clientSelect = document.getElementById('client_id');
    if (clientSelect && clientSelect.value) {
        formData.client_id = parseInt(clientSelect.value);
    }
    
    const url = currentEventId ? `/api/appointments/${currentEventId}` : '/api/appointments';
    const method = currentEventId ? 'PUT' : 'POST';
    
    fetch(url, {
        method: method,
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(formData)
    })
    .then(response => response.json())
    .then(data => {
        const modal = bootstrap.Modal.getInstance(document.getElementById('appointmentModal'));
        modal.hide();
        calendar.refetchEvents();
        loadStatistics();
        showToast(data.message || 'Cita guardada exitosamente', 'success');
    })
    .catch(error => {
        console.error('Error saving appointment:', error);
        showToast('Error al guardar la cita', 'danger');
    });
}

function setupEventListeners() {
    const deleteBtn = document.getElementById('deleteBtn');
    if (deleteBtn) {
        deleteBtn.addEventListener('click', function() {
            if (currentEventId && confirm('¿Está seguro de eliminar esta cita?')) {
                fetch(`/api/appointments/${currentEventId}`, {
                    method: 'DELETE'
                })
                .then(response => response.json())
                .then(data => {
                    const modal = bootstrap.Modal.getInstance(document.getElementById('appointmentModal'));
                    modal.hide();
                    calendar.refetchEvents();
                    loadStatistics();
                    showToast(data.message || 'Cita eliminada', 'success');
                })
                .catch(error => {
                    console.error('Error deleting appointment:', error);
                    showToast('Error al eliminar la cita', 'danger');
                });
            }
        });
    }
}

// ✅ CORREGIDO: Ahora también envía client_id al mover/redimensionar eventos
function updateEventDates(event) {
    const formData = {
        patient_name: event.extendedProps.patient_name,
        start_datetime: event.startStr.slice(0, 16),
        end_datetime: event.endStr ? event.endStr.slice(0, 16) : event.startStr.slice(0, 16),
        status: event.extendedProps.status,
        notes: event.extendedProps.notes || ''
    };
    
    // ✅ NUEVO: Mantener el client_id si existe
    if (event.extendedProps.client_id) {
        formData.client_id = event.extendedProps.client_id;
    }
    
    fetch(`/api/appointments/${event.id}`, {
        method: 'PUT',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(formData)
    })
    .then(response => response.json())
    .then(data => {
        showToast('Cita actualizada', 'success');
        loadStatistics();
    })
    .catch(error => {
        console.error('Error updating appointment:', error);
        showToast('Error al actualizar la cita', 'danger');
        calendar.refetchEvents();
    });
}

function loadStatistics() {
    fetch('/api/stats')
        .then(response => response.json())
        .then(data => {
            const roleBadge = document.querySelector('.role-badge');
            
            if (roleBadge && roleBadge.classList.contains('admin')) {
                document.getElementById('stat1').textContent = data.total_users || 0;
                document.getElementById('label1').textContent = 'Total Usuarios';
                
                document.getElementById('stat2').textContent = data.total_appointments || 0;
                document.getElementById('label2').textContent = 'Total Citas';
                
                document.getElementById('stat3').textContent = data.active_appointments || 0;
                document.getElementById('label3').textContent = 'Citas Activas';
            } else if (roleBadge && roleBadge.classList.contains('profesional')) {
                document.getElementById('stat1').textContent = data.my_appointments || 0;
                document.getElementById('label1').textContent = 'Mis Citas';
                
                document.getElementById('stat2').textContent = data.pending || 0;
                document.getElementById('label2').textContent = 'Pendientes';
                
                document.getElementById('stat3').textContent = data.completed || 0;
                document.getElementById('label3').textContent = 'Completadas';
            } else {
                document.getElementById('stat1').textContent = data.my_appointments || 0;
                document.getElementById('label1').textContent = 'Mis Citas';
                
                document.getElementById('stat2').textContent = data.upcoming || 0;
                document.getElementById('label2').textContent = 'Próximas';
                
                document.getElementById('stat3').textContent = 0;
                document.getElementById('label3').textContent = 'Historial';
            }
            
            animateCounters();
        })
        .catch(error => {
            console.error('Error loading statistics:', error);
        });
}

function animateCounters() {
    document.querySelectorAll('.stat-value').forEach(el => {
        const target = parseInt(el.textContent);
        let current = 0;
        const increment = target / 30;
        const timer = setInterval(() => {
            current += increment;
            if (current >= target) {
                el.textContent = target;
                clearInterval(timer);
            } else {
                el.textContent = Math.floor(current);
            }
        }, 30);
    });
}

function showToast(message, type) {
    const toastContainer = document.createElement('div');
    toastContainer.style.cssText = `
        position: fixed;
        top: 80px;
        right: 20px;
        z-index: 9999;
        animation: slideIn 0.3s ease-out;
    `;
    
    const alertClass = type === 'success' ? 'alert-success' : 
                      type === 'danger' ? 'alert-danger' : 
                      type === 'warning' ? 'alert-warning' : 'alert-info';
    
    const icon = type === 'success' ? 'fa-check-circle' : 
                 type === 'danger' ? 'fa-exclamation-circle' : 
                 type === 'warning' ? 'fa-exclamation-triangle' : 'fa-info-circle';
    
    toastContainer.innerHTML = `
        <div class="alert ${alertClass} alert-dismissible fade show" role="alert">
            <i class="fas ${icon} me-2"></i>${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `;
    
    document.body.appendChild(toastContainer);
    
    setTimeout(() => {
        toastContainer.style.animation = 'fadeOut 0.3s ease-out';
        setTimeout(() => toastContainer.remove(), 300);
    }, 3000);
}