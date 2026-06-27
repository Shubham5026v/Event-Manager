/**
 * EventX - Venue Booking Module
 * Main JavaScript file for venue management, booking, and calendar functionality
 * Version 2.0
 */

// ============================================
// Venue Management Functions
// ============================================

class VenueManager {
    constructor() {
        this.currentFilters = {
            status: 'all',
            type: 'all',
            capacity: 'all',
            search: ''
        };
        this.init();
    }

    init() {
        this.bindEvents();
        this.initFilters();
        this.initTooltips();
    }

    bindEvents() {
        // Filter events
        const typeFilter = document.getElementById('typeFilter');
        const capacityFilter = document.getElementById('capacityFilter');
        const searchInput = document.getElementById('searchInput');
        
        if (typeFilter) typeFilter.addEventListener('change', () => this.filterVenues());
        if (capacityFilter) capacityFilter.addEventListener('change', () => this.filterVenues());
        if (searchInput) searchInput.addEventListener('keyup', () => this.filterVenues());
        
        // Status filter cards
        document.querySelectorAll('.stat-card').forEach(card => {
            card.addEventListener('click', () => {
                const status = card.dataset.status;
                this.filterByStatus(status);
            });
        });
    }

    initFilters() {
        this.filterVenues();
    }

    initTooltips() {
        document.querySelectorAll('[data-tooltip]').forEach(el => {
            el.addEventListener('mouseenter', (e) => {
                const tooltip = document.createElement('div');
                tooltip.className = 'tooltip';
                tooltip.textContent = el.dataset.tooltip;
                tooltip.style.cssText = `
                    position: absolute;
                    background: rgba(8, 18, 34, 0.95);
                    backdrop-filter: blur(10px);
                    color: white;
                    padding: 0.3rem 0.8rem;
                    border-radius: 8px;
                    font-size: 0.75rem;
                    border: 1px solid rgba(0, 255, 255, 0.3);
                    z-index: 1000;
                    white-space: nowrap;
                `;
                document.body.appendChild(tooltip);
                const rect = el.getBoundingClientRect();
                tooltip.style.top = `${rect.top - tooltip.offsetHeight - 5}px`;
                tooltip.style.left = `${rect.left + (rect.width / 2) - (tooltip.offsetWidth / 2)}px`;
                el.addEventListener('mouseleave', () => tooltip.remove(), { once: true });
            });
        });
    }

    filterByStatus(status) {
        this.currentFilters.status = status;
        
        document.querySelectorAll('.stat-card').forEach(card => {
            if (card.dataset.status === status) {
                card.classList.add('active');
            } else {
                card.classList.remove('active');
            }
        });
        
        this.filterVenues();
    }

    filterVenues() {
        const typeFilter = document.getElementById('typeFilter');
        const capacityFilter = document.getElementById('capacityFilter');
        const searchInput = document.getElementById('searchInput');
        
        this.currentFilters.type = typeFilter ? typeFilter.value : 'all';
        this.currentFilters.capacity = capacityFilter ? capacityFilter.value : 'all';
        this.currentFilters.search = searchInput ? searchInput.value.toLowerCase() : '';
        
        const cards = document.querySelectorAll('.venue-card');
        let visibleCount = 0;
        
        cards.forEach(card => {
            let show = true;
            const status = card.dataset.status;
            const type = card.dataset.type;
            const capacity = parseInt(card.dataset.capacity);
            const name = card.dataset.name;
            
            if (this.currentFilters.status !== 'all' && status !== this.currentFilters.status) show = false;
            if (this.currentFilters.type !== 'all' && type !== this.currentFilters.type) show = false;
            
            if (this.currentFilters.capacity !== 'all') {
                if (this.currentFilters.capacity === '0-50' && capacity > 50) show = false;
                else if (this.currentFilters.capacity === '50-100' && (capacity < 50 || capacity > 100)) show = false;
                else if (this.currentFilters.capacity === '100-200' && (capacity < 100 || capacity > 200)) show = false;
                else if (this.currentFilters.capacity === '200-500' && (capacity < 200 || capacity > 500)) show = false;
                else if (this.currentFilters.capacity === '500+' && capacity < 500) show = false;
            }
            
            if (this.currentFilters.search && !name.includes(this.currentFilters.search)) show = false;
            
            card.style.display = show ? '' : 'none';
            if (show) visibleCount++;
        });
        
        this.updateEmptyState(visibleCount);
    }

    updateEmptyState(visibleCount) {
        const grid = document.getElementById('venuesGrid');
        const existingEmpty = grid?.querySelector('.empty-state');
        
        if (visibleCount === 0 && !existingEmpty) {
            const emptyDiv = document.createElement('div');
            emptyDiv.className = 'empty-state';
            emptyDiv.style.gridColumn = '1 / -1';
            emptyDiv.innerHTML = `
                <i class="fas fa-building"></i>
                <h3>No Venues Found</h3>
                <p>No venues match your search criteria.</p>
            `;
            grid?.appendChild(emptyDiv);
        } else if (visibleCount > 0 && existingEmpty) {
            existingEmpty.remove();
        }
    }

    async toggleVenueStatus(venueId, currentStatus) {
        const newStatus = currentStatus === 'active' ? 'maintenance' : 'active';
        const action = newStatus === 'active' ? 'activate' : 'put under maintenance';
        
        if (!confirm(`Are you sure you want to ${action} this venue?`)) return;
        
        try {
            const response = await fetch(`/venues/api/venues/${venueId}/status`, {
                method: 'PATCH',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify({ status: newStatus })
            });
            
            const data = await response.json();
            if (data.success) {
                window.EventX.showToast(`Venue ${newStatus === 'active' ? 'activated' : 'marked as maintenance'} successfully`, 'success');
                setTimeout(() => location.reload(), 1000);
            } else {
                window.EventX.showToast(data.error || 'Failed to update status', 'error');
            }
        } catch (error) {
            console.error('Error:', error);
            window.EventX.showToast('An error occurred', 'error');
        }
    }
}

// ============================================
// Booking Functions
// ============================================

class BookingManager {
    constructor() {
        this.availabilityCheckTimeout = null;
        this.selectedSlot = null;
        this.init();
    }

    init() {
        this.bindBookingEvents();
        this.initDatePickers();
    }

    bindBookingEvents() {
        const venueSelect = document.getElementById('venueSelect');
        const bookingDate = document.getElementById('bookingDate');
        const startTime = document.getElementById('startTime');
        const endTime = document.getElementById('endTime');
        
        if (venueSelect) venueSelect.addEventListener('change', () => this.debounceCheckAvailability());
        if (bookingDate) bookingDate.addEventListener('change', () => this.debounceCheckAvailability());
        if (startTime) startTime.addEventListener('change', () => this.debounceCheckAvailability());
        if (endTime) endTime.addEventListener('change', () => this.debounceCheckAvailability());
        
        const bookingForm = document.getElementById('bookingForm');
        if (bookingForm) {
            bookingForm.addEventListener('submit', (e) => this.handleBookingSubmit(e));
        }
    }

    initDatePickers() {
        const today = new Date().toISOString().split('T')[0];
        const maxDate = new Date();
        maxDate.setDate(maxDate.getDate() + 90);
        
        const datePicker = document.getElementById('bookingDate');
        if (datePicker) {
            datePicker.min = today;
            datePicker.max = maxDate.toISOString().split('T')[0];
        }
    }

    debounceCheckAvailability() {
        clearTimeout(this.availabilityCheckTimeout);
        this.availabilityCheckTimeout = setTimeout(() => this.checkAvailability(), 500);
    }

    async checkAvailability() {
        const venueId = document.getElementById('venueSelect')?.value;
        const date = document.getElementById('bookingDate')?.value;
        const startTime = document.getElementById('startTime')?.value;
        const endTime = document.getElementById('endTime')?.value;
        const statusDiv = document.getElementById('availabilityStatus');
        
        if (!venueId || !date || !startTime || !endTime) {
            if (statusDiv) {
                statusDiv.innerHTML = `<i class="fas fa-info-circle"></i><span>Select venue, date, and time to check availability</span>`;
                statusDiv.className = 'availability-status status-checking';
            }
            return;
        }
        
        if (startTime >= endTime) {
            if (statusDiv) {
                statusDiv.innerHTML = `<i class="fas fa-exclamation-triangle"></i><span>End time must be after start time</span>`;
                statusDiv.className = 'availability-status status-unavailable';
            }
            return;
        }
        
        if (statusDiv) {
            statusDiv.innerHTML = `<i class="fas fa-spinner fa-spin"></i><span>Checking availability...</span>`;
            statusDiv.className = 'availability-status status-checking';
        }
        
        try {
            const response = await fetch('/bookings/api/check-availability', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    venue_id: parseInt(venueId),
                    start_time: `${date}T${startTime}:00`,
                    end_time: `${date}T${endTime}:00`
                })
            });
            
            const data = await response.json();
            
            if (statusDiv) {
                if (data.available) {
                    statusDiv.innerHTML = `<i class="fas fa-check-circle"></i><span>✓ Venue is available for the selected time slot!</span>`;
                    statusDiv.className = 'availability-status status-available';
                } else {
                    statusDiv.innerHTML = `<i class="fas fa-times-circle"></i><span>✗ Venue is not available for the selected time slot.</span>`;
                    statusDiv.className = 'availability-status status-unavailable';
                }
            }
        } catch (error) {
            console.error('Error checking availability:', error);
            if (statusDiv) {
                statusDiv.innerHTML = `<i class="fas fa-exclamation-circle"></i><span>Failed to check availability. Please try again.</span>`;
                statusDiv.className = 'availability-status status-unavailable';
            }
        }
    }

    async handleBookingSubmit(e) {
        e.preventDefault();
        const submitBtn = document.getElementById('submitBtn');
        const originalText = submitBtn?.innerHTML;
        
        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Submitting...';
        }
        
        const formData = new FormData(e.target);
        
        try {
            const response = await fetch(window.location.href, {
                method: 'POST',
                body: formData
            });
            
            if (response.redirected) {
                window.location.href = response.url;
            } else {
                const data = await response.json();
                if (data.error) {
                    window.EventX.showToast(data.error, 'error');
                    if (submitBtn) {
                        submitBtn.disabled = false;
                        submitBtn.innerHTML = originalText;
                    }
                }
            }
        } catch (error) {
            console.error('Error:', error);
            window.EventX.showToast('An error occurred. Please try again.', 'error');
            if (submitBtn) {
                submitBtn.disabled = false;
                submitBtn.innerHTML = originalText;
            }
        }
    }

    selectTimeSlot(start, end) {
        this.selectedSlot = { start, end };
        document.querySelectorAll('.time-slot').forEach(el => {
            el.classList.remove('selected');
            if (el.dataset.start === start) el.classList.add('selected');
        });
        
        const infoDiv = document.getElementById('selectedSlotInfo');
        if (infoDiv) {
            infoDiv.innerHTML = `
                <i class="fas fa-check-circle"></i> Selected: ${start} - ${end}
                <button class="btn-book" onclick="window.bookingManager.proceedToBooking()" style="margin-left: 1rem; padding: 0.2rem 0.8rem; background: linear-gradient(135deg, #2b6eff, #9b4dff); border: none; border-radius: 20px; color: white; cursor: pointer;">
                    Proceed to Book
                </button>
            `;
        }
    }

    proceedToBooking() {
        if (!this.selectedSlot) return;
        const date = document.getElementById('datePicker')?.value;
        window.location.href = `/bookings/create?venue=${currentVenueId}&date=${date}&start=${this.selectedSlot.start}&end=${this.selectedSlot.end}`;
    }
}

// ============================================
// Calendar Functions
// ============================================

class CalendarManager {
    constructor() {
        this.calendar = null;
        this.init();
    }

    init() {
        this.initFullCalendar();
        this.bindCalendarEvents();
    }

    initFullCalendar() {
        const calendarEl = document.getElementById('calendar');
        if (!calendarEl || typeof FullCalendar === 'undefined') return;
        
        this.calendar = new FullCalendar.Calendar(calendarEl, {
            initialView: 'dayGridMonth',
            headerToolbar: {
                left: 'prev,next today',
                center: 'title',
                right: 'dayGridMonth,timeGridWeek,timeGridDay'
            },
            locale: 'en',
            timeZone: 'UTC',
            events: (fetchInfo, successCallback, failureCallback) => this.fetchEvents(fetchInfo, successCallback, failureCallback),
            eventClick: (info) => this.showEventDetails(info.event),
            dateClick: (info) => this.handleDateClick(info),
            eventDidMount: (info) => this.styleEvent(info),
            loading: (isLoading) => this.handleLoading(isLoading)
        });
        
        this.calendar.render();
    }

    bindCalendarEvents() {
        const venueFilter = document.getElementById('venueFilter');
        const eventTypeFilter = document.getElementById('eventTypeFilter');
        
        if (venueFilter) venueFilter.addEventListener('change', () => this.calendar?.refetchEvents());
        if (eventTypeFilter) eventTypeFilter.addEventListener('change', () => this.calendar?.refetchEvents());
    }

    async fetchEvents(fetchInfo, successCallback, failureCallback) {
        const venueId = document.getElementById('venueFilter')?.value || 'all';
        const eventType = document.getElementById('eventTypeFilter')?.value || 'all';
        
        let url = `/calendar/api/events?start=${fetchInfo.startStr}&end=${fetchInfo.endStr}`;
        if (venueId !== 'all') url += `&venue_id=${venueId}`;
        if (eventType !== 'all') url += `&event_type=${eventType}`;
        
        try {
            const response = await fetch(url);
            const data = await response.json();
            successCallback(data);
        } catch (error) {
            console.error('Error fetching events:', error);
            failureCallback(error);
        }
    }

    showEventDetails(event) {
        const modal = document.getElementById('eventModal');
        const detailsContainer = document.getElementById('eventDetails');
        const viewLink = document.getElementById('viewBookingLink');
        
        if (!modal) return;
        
        const startTime = event.start ? new Date(event.start).toLocaleString() : 'N/A';
        const endTime = event.end ? new Date(event.end).toLocaleString() : 'N/A';
        const venueName = event.extendedProps?.venue_name || 'N/A';
        const eventType = event.extendedProps?.event_type || 'N/A';
        const description = event.extendedProps?.description || 'No description provided';
        const attendees = event.extendedProps?.expected_attendees || 'Not specified';
        
        if (detailsContainer) {
            detailsContainer.innerHTML = `
                <div class="detail-row"><span class="detail-label">Event Title:</span><span class="detail-value">${this.escapeHtml(event.title)}</span></div>
                <div class="detail-row"><span class="detail-label">Venue:</span><span class="detail-value">${this.escapeHtml(venueName)}</span></div>
                <div class="detail-row"><span class="detail-label">Date & Time:</span><span class="detail-value">${startTime} - ${endTime}</span></div>
                <div class="detail-row"><span class="detail-label">Event Type:</span><span class="detail-value">${eventType.charAt(0).toUpperCase() + eventType.slice(1)}</span></div>
                <div class="detail-row"><span class="detail-label">Expected Attendees:</span><span class="detail-value">${attendees}</span></div>
                <div class="detail-row"><span class="detail-label">Description:</span><span class="detail-value">${this.escapeHtml(description)}</span></div>
            `;
        }
        
        if (viewLink) viewLink.href = `/bookings/${event.id}`;
        if (viewLink && event.extendedProps?.status !== 'confirmed') {
            viewLink.style.display = 'none';
        } else if (viewLink) {
            viewLink.style.display = 'inline-flex';
        }
        
        modal.classList.add('active');
    }

    handleDateClick(info) {
        const date = new Date(info.dateStr);
        const formattedDate = date.toISOString().split('T')[0];
        window.location.href = `/bookings/create?date=${formattedDate}`;
    }

    styleEvent(info) {
        const eventType = info.event.extendedProps?.event_type;
        if (eventType === 'academic') info.el.classList.add('fc-event-academic');
        else if (eventType === 'cultural') info.el.classList.add('fc-event-cultural');
        else info.el.classList.add('fc-event-practice');
    }

    handleLoading(isLoading) {
        const toolbar = document.querySelector('.fc-toolbar');
        if (toolbar) toolbar.style.opacity = isLoading ? '0.5' : '1';
    }

    closeEventModal() {
        const modal = document.getElementById('eventModal');
        if (modal) modal.classList.remove('active');
    }

    escapeHtml(str) {
        if (!str) return '';
        return str.replace(/[&<>]/g, (m) => {
            if (m === '&') return '&amp;';
            if (m === '<') return '&lt;';
            if (m === '>') return '&gt;';
            return m;
        });
    }
}

// ============================================
// Approval Functions
// ============================================

class ApprovalManager {
    constructor() {
        this.selectedApprovals = new Set();
        this.init();
    }

    init() {
        this.bindApprovalEvents();
    }

    bindApprovalEvents() {
        const selectAll = document.getElementById('selectAllCheckbox');
        if (selectAll) selectAll.addEventListener('change', () => this.toggleSelectAll());
    }

    updateSelection() {
        const checkboxes = document.querySelectorAll('.approval-select:checked');
        this.selectedApprovals.clear();
        checkboxes.forEach(cb => this.selectedApprovals.add(parseInt(cb.dataset.id)));
        
        const batchActions = document.getElementById('batchActions');
        const selectedCount = document.getElementById('selectedCount');
        
        if (batchActions && selectedCount) {
            if (this.selectedApprovals.size > 0) {
                batchActions.classList.remove('hidden');
                selectedCount.textContent = `${this.selectedApprovals.size} selected`;
            } else {
                batchActions.classList.add('hidden');
            }
        }
        
        const selectAll = document.getElementById('selectAllCheckbox');
        const allCheckboxes = document.querySelectorAll('.approval-select');
        if (selectAll) {
            selectAll.checked = this.selectedApprovals.size === allCheckboxes.length && allCheckboxes.length > 0;
        }
    }

    toggleSelectAll() {
        const selectAll = document.getElementById('selectAllCheckbox');
        const checkboxes = document.querySelectorAll('.approval-select');
        checkboxes.forEach(cb => cb.checked = selectAll.checked);
        this.updateSelection();
    }

    openApproveModal(approvalId, title) {
        this.currentApprovalId = approvalId;
        const titleEl = document.getElementById('approveBookingTitle');
        if (titleEl) titleEl.textContent = title;
        const modal = document.getElementById('approveModal');
        if (modal) modal.style.display = 'flex';
    }

    openRejectModal(approvalId, title) {
        this.currentApprovalId = approvalId;
        const titleEl = document.getElementById('rejectBookingTitle');
        if (titleEl) titleEl.textContent = title;
        const modal = document.getElementById('rejectModal');
        if (modal) modal.style.display = 'flex';
    }

    closeModals() {
        const approveModal = document.getElementById('approveModal');
        const rejectModal = document.getElementById('rejectModal');
        if (approveModal) approveModal.style.display = 'none';
        if (rejectModal) rejectModal.style.display = 'none';
        this.currentApprovalId = null;
    }

    submitApproval(action) {
        if (!this.currentApprovalId) return;
        
        let comments = '';
        if (action === 'approve') {
            comments = document.getElementById('approveComments')?.value || '';
        } else {
            comments = document.getElementById('rejectReason')?.value || '';
            if (!comments) {
                window.EventX.showToast('Please provide a reason for rejection', 'warning');
                return;
            }
        }
        
        const form = document.createElement('form');
        form.method = 'POST';
        form.action = `/approvals/${this.currentApprovalId}/process`;
        
        const actionInput = document.createElement('input');
        actionInput.type = 'hidden';
        actionInput.name = 'action';
        actionInput.value = action;
        form.appendChild(actionInput);
        
        const commentsInput = document.createElement('input');
        commentsInput.type = 'hidden';
        commentsInput.name = 'comments';
        commentsInput.value = comments;
        form.appendChild(commentsInput);
        
        document.body.appendChild(form);
        form.submit();
    }

    batchApprove() {
        if (this.selectedApprovals.size === 0) return;
        if (confirm(`Approve ${this.selectedApprovals.size} pending approval(s)?`)) {
            const form = document.createElement('form');
            form.method = 'POST';
            form.action = '/approvals/batch';
            
            const actionInput = document.createElement('input');
            actionInput.type = 'hidden';
            actionInput.name = 'action';
            actionInput.value = 'approve';
            form.appendChild(actionInput);
            
            this.selectedApprovals.forEach(id => {
                const input = document.createElement('input');
                input.type = 'hidden';
                input.name = 'approval_ids';
                input.value = id;
                form.appendChild(input);
            });
            
            document.body.appendChild(form);
            form.submit();
        }
    }

    batchReject() {
        if (this.selectedApprovals.size === 0) return;
        const reason = prompt('Please provide a reason for rejection:');
        if (reason === null) return;
        
        const form = document.createElement('form');
        form.method = 'POST';
        form.action = '/approvals/batch';
        
        const actionInput = document.createElement('input');
        actionInput.type = 'hidden';
        actionInput.name = 'action';
        actionInput.value = 'reject';
        form.appendChild(actionInput);
        
        const commentsInput = document.createElement('input');
        commentsInput.type = 'hidden';
        commentsInput.name = 'comments';
        commentsInput.value = reason;
        form.appendChild(commentsInput);
        
        this.selectedApprovals.forEach(id => {
            const input = document.createElement('input');
            input.type = 'hidden';
            input.name = 'approval_ids';
            input.value = id;
            form.appendChild(input);
        });
        
        document.body.appendChild(form);
        form.submit();
    }
}

// ============================================
// Initialize on DOM Load
// ============================================

document.addEventListener('DOMContentLoaded', () => {
    window.venueManager = new VenueManager();
    window.bookingManager = new BookingManager();
    window.calendarManager = new CalendarManager();
    window.approvalManager = new ApprovalManager();
    
    // Close modals on ESC
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            if (window.calendarManager) window.calendarManager.closeEventModal();
            if (window.approvalManager) window.approvalManager.closeModals();
        }
    });
});

// ============================================
// Global Functions for HTML Event Handlers
// ============================================

window.filterByStatus = (status) => window.venueManager?.filterByStatus(status);
window.filterVenues = () => window.venueManager?.filterVenues();
window.toggleVenueStatus = (id, status) => window.venueManager?.toggleVenueStatus(id, status);
window.selectTimeSlot = (start, end) => window.bookingManager?.selectTimeSlot(start, end);
window.proceedToBooking = () => window.bookingManager?.proceedToBooking();
window.closeEventModal = () => window.calendarManager?.closeEventModal();
window.openApproveModal = (id, title) => window.approvalManager?.openApproveModal(id, title);
window.openRejectModal = (id, title) => window.approvalManager?.openRejectModal(id, title);
window.closeApproveModal = () => window.approvalManager?.closeModals();
window.closeRejectModal = () => window.approvalManager?.closeModals();
window.submitApproval = (action) => window.approvalManager?.submitApproval(action);
window.batchApprove = () => window.approvalManager?.batchApprove();
window.batchReject = () => window.approvalManager?.batchReject();
window.updateSelection = () => window.approvalManager?.updateSelection();
window.toggleSelectAll = () => window.approvalManager?.toggleSelectAll();