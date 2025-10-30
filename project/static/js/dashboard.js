let calendar;
let currentEventId = null;

document.addEventListener('DOMContentLoaded', function() {
    initializeCalendar();
    loadStatistics();
    setupEventListeners();
    loadClients();
    loadAppointmentsList();  // ✅ NUEVO: Cargar lista de citas
});

function loadClients() {
    const roleBadge = document.querySelector('.role-badge');
    if (!roleBadge || (!roleBadge.classList.contains('profesional') && !roleBadge.classList.contains('admin'))) {
        return;
    }
    
    fetch('/api/clients')
        .then(response => {
            if (!response.ok) throw new Error('No autorizado');
            return response.json();
        })
        .then(clients => {
            const clientSelect = document.getElementById('client_id');
            if (clientSelect) {
                clientSelect.innerHTML = '<option value="">-- Sin asignar --</option>';
                clients.forEach(client => {
                    const option = document.createElement('option');
                    option.value = client.id;
                    option.textContent = `${client.username} (${client.email})`;
                    clientSelect.appendChild(option);
                });
            }
        })
        .catch(error => console.error('Error loading clients:', error));
}

function initializeCalendar() {
    const calendarEl = document.getElementById('calendar-container');
    
    calendar = new FullCalendar.Calendar(calendarEl, {
        initialView: 'dayGridMonth',
        locale: 'es',
        timeZone: 'America/Lima',  // ✅ FIX: Zona horaria de Perú
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
            fetch(`/api/appointments`)
                .then(response => {
                    if (!response.ok) throw new Error('Error al cargar citas');
                    return response.json();
                })
                .then(data => {
                    successCallback(data);
                })
                .catch(error => {
                    console.error('Error fetching appointments:', error);
                    showToast('Error al cargar las citas', 'danger');
                    failureCallback(error);
                });
        },
        
        select: function(info) {
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
        },
        
        eventDidMount: function(info) {
            info.el.title = `${info.event.title}\n${info.event.extendedProps.status}\n${new Date(info.event.start).toLocaleString('es-PE')}`;
        }
    });
    
    calendar.render();
}

function openNewAppointmentModal() {
    currentEventId = null;
    const now = new Date();
    const startStr = formatDateTimeLocal(now);
    const endDate = new Date(now.getTime() + 60 * 60 * 1000);
    const endStr = formatDateTimeLocal(endDate);
    openAppointmentModal(startStr, endStr);
}

function openAppointmentModal(startStr, endStr) {
    const modal = new bootstrap.Modal(document.getElementById('appointmentModal'));
    const modalTitle = document.getElementById('modalTitle');
    const form = document.getElementById('appointmentForm');
    const deleteBtn = document.getElementById('deleteBtn');
    
    modalTitle.innerHTML = '<i class="fas fa-calendar-plus"></i> Añadir Cita';
    form.reset();
    
    document.getElementById('patient_name').value = '';
    document.getElementById('start_datetime').value = formatDateTimeLocal(new Date(startStr));
    document.getElementById('end_datetime').value = formatDateTimeLocal(new Date(endStr));
    document.getElementById('notes').value = '';
    
    const clientSelect = document.getElementById('client_id');
    if (clientSelect) {
        clientSelect.value = '';
    }
    
    deleteBtn.style.display = 'none';
    modal.show();
}

function showAppointmentDetails(event) {
    const modal = new bootstrap.Modal(document.getElementById('appointmentModal'));
    const modalTitle = document.getElementById('modalTitle');
    const deleteBtn = document.getElementById('deleteBtn');
    
    modalTitle.innerHTML = '<i class="fas fa-calendar-edit"></i> Editar Cita';
    
    document.getElementById('patient_name').value = event.extendedProps.patient_name;
    document.getElementById('notes').value = event.extendedProps.notes || '';
    document.getElementById('start_datetime').value = formatDateTimeLocal(new Date(event.start));
    document.getElementById('end_datetime').value = formatDateTimeLocal(new Date(event.end || event.start));
    
    const clientSelect = document.getElementById('client_id');
    if (clientSelect && event.extendedProps.client_id) {
        clientSelect.value = event.extendedProps.client_id;
    } else if (clientSelect) {
        clientSelect.value = '';
    }
    
    // ✅ Solo admin puede eliminar
    const roleBadge = document.querySelector('.role-badge');
    deleteBtn.style.display = roleBadge && roleBadge.classList.contains('admin') ? 'inline-block' : 'none';
    
    modal.show();
}

function saveAppointment() {
    const patientName = document.getElementById('patient_name').value.trim();
    const startStr = document.getElementById('start_datetime').value;
    const endStr = document.getElementById('end_datetime').value;
    const notes = document.getElementById('notes').value;
    
    if (!patientName) {
        showToast('El nombre del paciente es requerido', 'warning');
        return;
    }
    
    if (!startStr || !endStr) {
        showToast('Las fechas de inicio y fin son requeridas', 'warning');
        return;
    }
    
    const startDate = new Date(startStr);
    const endDate = new Date(endStr);
    
    if (endDate <= startDate) {
        showToast('La fecha de fin debe ser posterior a la fecha de inicio', 'warning');
        return;
    }
    
    // ✅ FIX: Enviar en formato ISO con zona horaria
    const formData = {
        patient_name: patientName,
        start_datetime: startDate.toISOString(),
        end_datetime: endDate.toISOString(),
        notes: notes
    };
    
    const clientSelect = document.getElementById('client_id');
    if (clientSelect && clientSelect.value) {
        formData.client_id = parseInt(clientSelect.value);
    }
    
    const url = currentEventId ? `/api/appointments/${currentEventId}` : '/api/appointments';
    const method = currentEventId ? 'PUT' : 'POST';
    
    const saveBtn = document.querySelector('#appointmentModal .btn-primary');
    const originalText = saveBtn.innerHTML;
    saveBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Guardando...';
    saveBtn.disabled = true;
    
    fetch(url, {
        method: method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData)
    })
    .then(response => response.json().then(data => ({ ok: response.ok, status: response.status, data })))
    .then(({ok, status, data}) => {
        if (!ok) {
            if (status === 400 && data.error) {
                if (data.error.includes('solapa')) {
                    showToast(`⚠️ ${data.error}`, 'danger');
                } else {
                    showToast(data.error, 'warning');
                }
            } else {
                showToast('Error al guardar la cita', 'danger');
            }
            throw new Error(data.error || 'Error desconocido');
        }
        
        const modal = bootstrap.Modal.getInstance(document.getElementById('appointmentModal'));
        modal.hide();
        calendar.refetchEvents();
        loadStatistics();
        loadAppointmentsList();  // ✅ Refrescar lista
        showToast(data.message || 'Cita guardada exitosamente', 'success');
    })
    .catch(error => console.error('Error saving appointment:', error))
    .finally(() => {
        saveBtn.innerHTML = originalText;
        saveBtn.disabled = false;
    });
}

function setupEventListeners() {
    const deleteBtn = document.getElementById('deleteBtn');
    if (deleteBtn) {
        deleteBtn.addEventListener('click', function() {
            if (currentEventId && confirm('⚠️ ¿Está seguro de ELIMINAR PERMANENTEMENTE esta cita?\n\nEsta acción no se puede deshacer.')) {
                fetch(`/api/appointments/${currentEventId}`, { method: 'DELETE' })
                    .then(response => response.json())
                    .then(data => {
                        const modal = bootstrap.Modal.getInstance(document.getElementById('appointmentModal'));
                        modal.hide();
                        calendar.refetchEvents();
                        loadStatistics();
                        loadAppointmentsList();
                        showToast(data.message || 'Cita eliminada permanentemente', 'success');
                    })
                    .catch(error => {
                        console.error('Error deleting appointment:', error);
                        showToast('Error al eliminar la cita', 'danger');
                    });
            }
        });
    }
}

function updateEventDates(event) {
    const formData = {
        patient_name: event.extendedProps.patient_name,
        start_datetime: new Date(event.start).toISOString(),
        end_datetime: new Date(event.end || event.start).toISOString(),
        notes: event.extendedProps.notes || ''
    };
    
    if (event.extendedProps.client_id) {
        formData.client_id = event.extendedProps.client_id;
    }
    
    fetch(`/api/appointments/${event.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData)
    })
    .then(response => response.json().then(data => ({ ok: response.ok, data })))
    .then(({ok, data}) => {
        if (!ok) {
            calendar.refetchEvents();
            showToast(data.error && data.error.includes('solapa') ? `⚠️ ${data.error}` : 'Error al actualizar la cita', 'danger');
        } else {
            showToast('Cita actualizada', 'success');
            loadStatistics();
            loadAppointmentsList();
        }
    })
    .catch(error => {
        console.error('Error updating appointment:', error);
        showToast('Error al actualizar la cita', 'danger');
        calendar.refetchEvents();
    });
}

// ✅ NUEVO: Cargar lista de citas con acciones
function loadAppointmentsList() {
    const roleBadge = document.querySelector('.role-badge');
    if (!roleBadge || (!roleBadge.classList.contains('profesional') && !roleBadge.classList.contains('admin'))) {
        return;
    }
    
    const listContainer = document.getElementById('appointments-list');
    if (!listContainer) return;
    
    listContainer.innerHTML = '<div class="text-center py-3"><i class="fas fa-spinner fa-spin"></i> Cargando...</div>';
    
    fetch('/api/appointments')
        .then(response => response.json())
        .then(events => {
            if (events.length === 0) {
                listContainer.innerHTML = '<div class="text-center text-muted py-4">No hay citas programadas</div>';
                return;
            }
            
            listContainer.innerHTML = '';
            events.forEach(event => {
                const apt = event.extendedProps;
                const startDate = new Date(event.start);
                const isPast = apt.can_complete;
                
                const card = document.createElement('div');
                card.className = 'appointment-card mb-3';
                card.innerHTML = `
                    <div class="d-flex justify-content-between align-items-center">
                        <div class="flex-grow-1">
                            <h6 class="mb-1">${event.title}</h6>
                            <small class="text-muted">
                                <i class="far fa-calendar"></i> ${startDate.toLocaleDateString('es-PE')}
                                <i class="far fa-clock ms-2"></i> ${startDate.toLocaleTimeString('es-PE', {hour: '2-digit', minute: '2-digit'})}
                            </small>
                            ${apt.client && apt.client !== 'N/A' ? `<br><small class="text-muted"><i class="fas fa-user"></i> ${apt.client}</small>` : ''}
                            <br><span class="badge bg-${apt.status === 'completada' ? 'success' : 'primary'}">${apt.status.toUpperCase()}</span>
                        </div>
                        <div class="btn-group btn-group-sm">
                            ${apt.can_complete && apt.status === 'programada' ? 
                                `<button class="btn btn-success" onclick="completeAppointment(${event.id})" title="Marcar como completada">
                                    <i class="fas fa-check"></i>
                                </button>` : ''}
                            ${apt.can_cancel && apt.status === 'programada' ?
                                `<button class="btn btn-danger" onclick="cancelAppointment(${event.id}, '${event.title}')" title="Cancelar cita">
                                    <i class="fas fa-times"></i>
                                </button>` : ''}
                        </div>
                    </div>
                `;
                listContainer.appendChild(card);
            });
        })
        .catch(error => {
            console.error('Error loading appointments list:', error);
            listContainer.innerHTML = '<div class="text-center text-danger py-3">Error al cargar citas</div>';
        });
}

// ✅ NUEVO: Completar cita
function completeAppointment(id) {
    if (!confirm('¿Marcar esta cita como completada?')) return;
    
    fetch(`/api/appointments/${id}/complete`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
    })
    .then(response => response.json().then(data => ({ ok: response.ok, data })))
    .then(({ok, data}) => {
        if (!ok) {
            showToast(data.error || 'Error al completar la cita', 'danger');
        } else {
            calendar.refetchEvents();
            loadStatistics();
            loadAppointmentsList();
            showToast('✅ Cita marcada como completada', 'success');
        }
    })
    .catch(error => {
        console.error('Error completing appointment:', error);
        showToast('Error al completar la cita', 'danger');
    });
}

// ✅ NUEVO: Cancelar cita con confirmación
function cancelAppointment(id, patientName) {
    const reason = prompt(`¿Por qué deseas cancelar la cita de ${patientName}?\n\n(Opcional, presiona OK para continuar)`);
    
    if (reason === null) return; // Usuario canceló
    
    fetch(`/api/appointments/${id}/cancel`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason: reason || 'Sin motivo especificado' })
    })
    .then(response => response.json().then(data => ({ ok: response.ok, data })))
    .then(({ok, data}) => {
        if (!ok) {
            showToast(data.error || 'Error al cancelar la cita', 'danger');
        } else {
            calendar.refetchEvents();
            loadStatistics();
            loadAppointmentsList();
            loadCancelledAppointments();  // Refrescar historial de canceladas
            showToast('❌ Cita cancelada exitosamente', 'success');
        }
    })
    .catch(error => {
        console.error('Error cancelling appointment:', error);
        showToast('Error al cancelar la cita', 'danger');
    });
}

// ✅ NUEVO: Cargar citas canceladas
function loadCancelledAppointments() {
    const roleBadge = document.querySelector('.role-badge');
    if (!roleBadge || (!roleBadge.classList.contains('profesional') && !roleBadge.classList.contains('admin'))) {
        return;
    }
    
    const container = document.getElementById('cancelled-list');
    if (!container) return;
    
    container.innerHTML = '<div class="text-center py-3"><i class="fas fa-spinner fa-spin"></i> Cargando...</div>';
    
    fetch('/api/appointments/cancelled')
        .then(response => response.json())
        .then(appointments => {
            if (appointments.length === 0) {
                container.innerHTML = '<div class="text-center text-muted py-4">No hay citas canceladas</div>';
                return;
            }
            
            container.innerHTML = '';
            appointments.forEach(apt => {
                const cancelledDate = new Date(apt.cancelled_at);
                const aptDate = new Date(apt.start_datetime);
                
                const card = document.createElement('div');
                card.className = 'cancelled-card mb-3';
                card.innerHTML = `
                    <div>
                        <h6 class="mb-1 text-muted"><del>${apt.patient_name}</del></h6>
                        <small class="text-muted">
                            <i class="far fa-calendar"></i> Programada: ${aptDate.toLocaleDateString('es-PE')} ${aptDate.toLocaleTimeString('es-PE', {hour: '2-digit', minute: '2-digit'})}
                        </small>
                        <br><small class="text-danger">
                            <i class="fas fa-ban"></i> Cancelada: ${cancelledDate.toLocaleDateString('es-PE')} ${cancelledDate.toLocaleTimeString('es-PE', {hour: '2-digit', minute: '2-digit'})}
                        </small>
                        ${apt.cancellation_reason ? `<br><small class="text-muted"><i class="fas fa-info-circle"></i> ${apt.cancellation_reason}</small>` : ''}
                    </div>
                `;
                container.appendChild(card);
            });
        })
        .catch(error => {
            console.error('Error loading cancelled appointments:', error);
            container.innerHTML = '<div class="text-center text-danger py-3">Error al cargar historial</div>';
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
        .catch(error => console.error('Error loading statistics:', error));
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

function formatDateTimeLocal(date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    return `${year}-${month}-${day}T${hours}:${minutes}`;
}

function showToast(message, type) {
    const toastContainer = document.createElement('div');
    toastContainer.style.cssText = `
        position: fixed;
        top: 80px;
        right: 20px;
        z-index: 9999;
        animation: slideIn 0.3s ease-out;
        max-width: 400px;
    `;
    
    const alertClass = type === 'success' ? 'alert-success' : 
                      type === 'danger' ? 'alert-danger' : 
                      type === 'warning' ? 'alert-warning' : 'alert-info';
    
    const icon = type === 'success' ? 'fa-check-circle' : 
                 type === 'danger' ? 'fa-exclamation-circle' : 
                 type === 'warning' ? 'fa-exclamation-triangle' : 'fa-info-circle';
    
    const formattedMessage = message.replace(/\n/g, '<br>');
    
    toastContainer.innerHTML = `
        <div class="alert ${alertClass} alert-dismissible fade show" role="alert">
            <i class="fas ${icon} me-2"></i>${formattedMessage}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `;
    
    document.body.appendChild(toastContainer);
    
    const duration = message.length > 100 ? 6000 : 3000;
    
    setTimeout(() => {
        toastContainer.style.animation = 'fadeOut 0.3s ease-out';
        setTimeout(() => toastContainer.remove(), 300);
    }, duration);
}

// ✅ Cargar historial de canceladas al inicio
if (document.getElementById('cancelled-list')) {
    loadCancelledAppointments();
}
