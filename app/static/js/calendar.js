/**
 * EventX - Calendar Module
 * Handles calendar views, event management, and external calendar integration
 * Version 2.0
 */

// ============================================
// Calendar Manager Class
// ============================================

class CalendarManager {
    constructor(options = {}) {
        this.calendar = null;
        this.currentView = options.defaultView || 'dayGridMonth';
        this.currentDate = options.currentDate || new Date();
        this.venueId = options.venueId || null;
        this.eventSource = options.eventSource || '/calendar/api/events';
        this.calendarEl = document.getElementById(options.calendarElement || 'calendar');
        
        // Event handlers
        this.onEventClick = options.onEventClick || null;
        this.onDateClick = options.onDateClick || null;
        this.onEventDrop = options.onEventDrop || null;
        this.onEventResize = options.onEventResize || null;
        
        this.init();
    }

    init() {
        if (!this.calendarEl) return;
        this.initFullCalendar();
        this.bindEventListeners();
        this.loadUserSettings();
    }

    initFullCalendar() {
        if (typeof FullCalendar === 'undefined') {
            console.error('FullCalendar library not loaded');
            return;
        }

        this.calendar = new FullCalendar.Calendar(this.calendarEl, {
            initialView: this.currentView,
            initialDate: this.currentDate,
            headerToolbar: {
                left: 'prev,next today',
                center: 'title',
                right: 'dayGridMonth,timeGridWeek,timeGridDay,listWeek'
            },
            locale: 'en',
            timeZone: 'local',
            editable: true,
            selectable: true,
            selectMirror: true,
            dayMaxEvents: true,
            weekends: true,
            nowIndicator: true,
            height: 'auto',
            slotMinTime: '08:00:00',
            slotMaxTime: '22:00:00',
            allDaySlot: false,
            slotDuration: '00:30:00',
            snapDuration: '00:30:00',
            
            // Event sources
            events: (fetchInfo, successCallback, failureCallback) => {
                this.fetchEvents(fetchInfo, successCallback, failureCallback);
            },
            
            // Event handlers
            eventClick: (info) => this.handleEventClick(info),
            dateClick: (info) => this.handleDateClick(info),
            eventDrop: (info) => this.handleEventDrop(info),
            eventResize: (info) => this.handleEventResize(info),
            select: (info) => this.handleDateSelect(info),
            
            // Custom rendering
            eventDidMount: (info) => this.styleEvent(info),
            eventContent: (arg) => this.customEventContent(arg),
            
            // Loading state
            loading: (isLoading) => this.handleLoading(isLoading),
            
            // Views configuration
            views: {
                timeGridWeek: {
                    titleFormat: { year: 'numeric', month: 'long', day: 'numeric' },
                    columnHeaderFormat: { weekday: 'short' }
                },
                dayGridMonth: {
                    titleFormat: { year: 'numeric', month: 'long' },
                    dayHeaderFormat: { weekday: 'short' }
                }
            },
            
            // Button text
            buttonText: {
                today: 'Today',
                month: 'Month',
                week: 'Week',
                day: 'Day',
                list: 'List'
            }
        });
        
        this.calendar.render();
        this.setupPrintStyles();
    }

    bindEventListeners() {
        // View change listeners
        const viewButtons = document.querySelectorAll('[data-calendar-view]');
        viewButtons.forEach(btn => {
            btn.addEventListener('click', (e) => {
                const view = btn.dataset.calendarView;
                this.changeView(view);
            });
        });
        
        // Date navigation
        const prevBtn = document.getElementById('calendarPrev');
        const nextBtn = document.getElementById('calendarNext');
        const todayBtn = document.getElementById('calendarToday');
        
        if (prevBtn) prevBtn.addEventListener('click', () => this.prev());
        if (nextBtn) nextBtn.addEventListener('click', () => this.next());
        if (todayBtn) todayBtn.addEventListener('click', () => this.today());
        
        // Filter listeners
        const venueFilter = document.getElementById('venueFilter');
        const eventTypeFilter = document.getElementById('eventTypeFilter');
        
        if (venueFilter) venueFilter.addEventListener('change', () => this.refreshEvents());
        if (eventTypeFilter) eventTypeFilter.addEventListener('change', () => this.refreshEvents());
        
        // Export buttons
        const exportIcalBtn = document.getElementById('exportIcal');
        const exportGoogleBtn = document.getElementById('exportGoogle');
        
        if (exportIcalBtn) exportIcalBtn.addEventListener('click', () => this.exportToICal());
        if (exportGoogleBtn) exportGoogleBtn.addEventListener('click', () => this.syncWithGoogle());
    }

    async fetchEvents(fetchInfo, successCallback, failureCallback) {
        const venueId = document.getElementById('venueFilter')?.value || this.venueId || 'all';
        const eventType = document.getElementById('eventTypeFilter')?.value || 'all';
        
        let url = `${this.eventSource}?start=${fetchInfo.startStr}&end=${fetchInfo.endStr}`;
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

    handleEventClick(info) {
        const event = info.event;
        const modal = document.getElementById('eventModal');
        
        if (modal) {
            this.showEventDetails(event);
            modal.classList.add('active');
        }
        
        if (this.onEventClick) this.onEventClick(event);
    }

    handleDateClick(info) {
        if (this.onDateClick) {
            this.onDateClick(info.dateStr);
        } else {
            const date = new Date(info.dateStr);
            const formattedDate = date.toISOString().split('T')[0];
            window.location.href = `/bookings/create?date=${formattedDate}`;
        }
    }

    handleDateSelect(info) {
        const start = info.start;
        const end = info.end;
        const startStr = start.toISOString();
        const endStr = end.toISOString();
        
        if (confirm(`Create a new booking on ${start.toLocaleDateString()} from ${start.toLocaleTimeString()} to ${end.toLocaleTimeString()}?`)) {
            window.location.href = `/bookings/create?start=${startStr}&end=${endStr}`;
        }
    }

    handleEventDrop(info) {
        const event = info.event;
        const oldStart = info.oldEvent.start;
        const newStart = event.start;
        
        if (confirm(`Move "${event.title}" to ${newStart.toLocaleString()}?`)) {
            this.updateEventTime(event.id, event.start, event.end);
        } else {
            info.revert();
        }
        
        if (this.onEventDrop) this.onEventDrop(info);
    }

    handleEventResize(info) {
        const event = info.event;
        
        if (confirm(`Resize "${event.title}" to end at ${event.end.toLocaleTimeString()}?`)) {
            this.updateEventTime(event.id, event.start, event.end);
        } else {
            info.revert();
        }
        
        if (this.onEventResize) this.onEventResize(info);
    }

    async updateEventTime(eventId, start, end) {
        try {
            const response = await fetch(`/calendar/api/events/${eventId}/move`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify({
                    start: start.toISOString(),
                    end: end.toISOString()
                })
            });
            
            const data = await response.json();
            if (data.success) {
                this.showToast('Event updated successfully', 'success');
                this.refreshEvents();
            } else {
                this.showToast(data.error || 'Failed to update event', 'error');
            }
        } catch (error) {
            console.error('Error updating event:', error);
            this.showToast('An error occurred', 'error');
        }
    }

    showEventDetails(event) {
        const modal = document.getElementById('eventModal');
        const detailsContainer = document.getElementById('eventDetails');
        const viewLink = document.getElementById('viewBookingLink');
        
        if (!detailsContainer) return;
        
        const startTime = event.start ? new Date(event.start).toLocaleString() : 'N/A';
        const endTime = event.end ? new Date(event.end).toLocaleString() : 'N/A';
        const venueName = event.extendedProps?.venue_name || 'N/A';
        const eventType = event.extendedProps?.event_type || 'N/A';
        const description = event.extendedProps?.description || 'No description provided';
        const attendees = event.extendedProps?.expected_attendees || 'Not specified';
        const priority = event.extendedProps?.priority_name || 'Standard';
        
        detailsContainer.innerHTML = `
            <div class="detail-row">
                <span class="detail-label">Event Title:</span>
                <span class="detail-value">${this.escapeHtml(event.title)}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Venue:</span>
                <span class="detail-value">${this.escapeHtml(venueName)}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Date & Time:</span>
                <span class="detail-value">${startTime} - ${endTime}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Event Type:</span>
                <span class="detail-value">${eventType.charAt(0).toUpperCase() + eventType.slice(1)}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Priority:</span>
                <span class="detail-value priority-${event.extendedProps?.priority === 1 ? 'high' : event.extendedProps?.priority === 2 ? 'medium' : 'low'}">
                    ${priority}
                </span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Expected Attendees:</span>
                <span class="detail-value">${attendees}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Description:</span>
                <span class="detail-value">${this.escapeHtml(description)}</span>
            </div>
        `;
        
        if (viewLink) {
            viewLink.href = `/bookings/${event.id}`;
            if (event.extendedProps?.status !== 'confirmed') {
                viewLink.style.display = 'none';
            } else {
                viewLink.style.display = 'inline-flex';
            }
        }
    }

    styleEvent(info) {
        const eventType = info.event.extendedProps?.event_type;
        const priority = info.event.extendedProps?.priority;
        
        if (eventType === 'academic') {
            info.el.classList.add('fc-event-academic');
        } else if (eventType === 'cultural') {
            info.el.classList.add('fc-event-cultural');
        } else {
            info.el.classList.add('fc-event-practice');
        }
        
        if (priority === 1) {
            info.el.style.borderLeft = '4px solid #ff3366';
        } else if (priority === 2) {
            info.el.style.borderLeft = '4px solid #ffaa33';
        } else {
            info.el.style.borderLeft = '4px solid #00ff88';
        }
    }

    customEventContent(arg) {
        const event = arg.event;
        const time = event.start ? event.start.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '';
        
        return {
            html: `
                <div class="fc-event-title-container">
                    <strong>${this.escapeHtml(event.title)}</strong>
                    <div class="fc-event-time">${time}</div>
                </div>
            `
        };
    }

    handleLoading(isLoading) {
        const loader = document.getElementById('calendarLoader');
        if (loader) {
            loader.style.display = isLoading ? 'flex' : 'none';
        }
    }

    setupPrintStyles() {
        const style = document.createElement('style');
        style.textContent = `
            @media print {
                .fc-header-toolbar,
                .fc-toolbar-chunk:first-child,
                .fc-toolbar-chunk:last-child {
                    display: none !important;
                }
                .fc-daygrid-day {
                    break-inside: avoid;
                }
                .fc-event {
                    print-color-adjust: exact;
                    -webkit-print-color-adjust: exact;
                }
            }
        `;
        document.head.appendChild(style);
    }

    // ============================================
    // Public API Methods
    // ============================================

    changeView(view) {
        if (this.calendar) {
            this.calendar.changeView(view);
            this.currentView = view;
            this.saveUserSettings();
        }
    }

    prev() {
        if (this.calendar) this.calendar.prev();
    }

    next() {
        if (this.calendar) this.calendar.next();
    }

    today() {
        if (this.calendar) this.calendar.today();
    }

    goToDate(date) {
        if (this.calendar) this.calendar.gotoDate(date);
    }

    refreshEvents() {
        if (this.calendar) this.calendar.refetchEvents();
    }

    addEvent(eventData) {
        if (this.calendar) this.calendar.addEvent(eventData);
    }

    removeEvent(eventId) {
        const event = this.calendar.getEventById(eventId);
        if (event) event.remove();
    }

    updateEvent(eventId, eventData) {
        const event = this.calendar.getEventById(eventId);
        if (event) {
            event.setProp('title', eventData.title);
            if (eventData.start) event.setStart(eventData.start);
            if (eventData.end) event.setEnd(eventData.end);
        }
    }

    getEvents() {
        return this.calendar ? this.calendar.getEvents() : [];
    }

    // ============================================
    // Export & Sync Methods
    // ============================================

    async exportToICal() {
        const start = this.calendar.view.activeStart.toISOString();
        const end = this.calendar.view.activeEnd.toISOString();
        const venueId = document.getElementById('venueFilter')?.value || 'all';
        
        window.location.href = `/calendar/export?start=${start}&end=${end}&venue_id=${venueId}`;
    }

    async syncWithGoogle() {
        const events = this.getEvents();
        const googleCalendarUrl = 'https://www.google.com/calendar/render?action=TEMPLATE';
        
        events.forEach(event => {
            const start = event.start.toISOString().replace(/[-:]/g, '').split('.')[0] + 'Z';
            const end = event.end.toISOString().replace(/[-:]/g, '').split('.')[0] + 'Z';
            const url = `${googleCalendarUrl}&text=${encodeURIComponent(event.title)}&dates=${start}/${end}`;
            window.open(url, '_blank');
        });
    }

    async addToGoogleCalendar(eventId) {
        window.location.href = `/calendar/google/add/${eventId}`;
    }

    async addToOutlook(eventId) {
        window.location.href = `/calendar/outlook/add/${eventId}`;
    }

    async downloadAppleCalendar(eventId) {
        window.location.href = `/calendar/apple/download/${eventId}`;
    }

    // ============================================
    // Settings Methods
    // ============================================

    async loadUserSettings() {
        try {
            const response = await fetch('/calendar/api/settings');
            const settings = await response.json();
            
            if (settings.default_view) {
                this.changeView(settings.default_view);
            }
            if (settings.working_hours_start && settings.working_hours_end) {
                this.calendar.setOption('slotMinTime', settings.working_hours_start);
                this.calendar.setOption('slotMaxTime', settings.working_hours_end);
            }
            if (settings.show_weekends === false) {
                this.calendar.setOption('weekends', false);
            }
        } catch (error) {
            console.error('Error loading user settings:', error);
        }
    }

    async saveUserSettings(settings) {
        try {
            const response = await fetch('/calendar/api/settings', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify(settings)
            });
            
            const data = await response.json();
            if (data.success) {
                this.showToast('Settings saved successfully', 'success');
            }
        } catch (error) {
            console.error('Error saving settings:', error);
        }
    }

    // ============================================
    // Availability Methods
    // ============================================

    async checkAvailability(venueId, date, duration = 60) {
        try {
            const response = await fetch(`/calendar/api/available-slots?venue_id=${venueId}&date=${date}&duration=${duration}`);
            const data = await response.json();
            return data.slots;
        } catch (error) {
            console.error('Error checking availability:', error);
            return [];
        }
    }

    async getWeeklyAvailability(venueId, weekStart) {
        try {
            const response = await fetch('/calendar/api/availability/week', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ venue_id: venueId, week_start: weekStart })
            });
            const data = await response.json();
            return data.availability;
        } catch (error) {
            console.error('Error getting weekly availability:', error);
            return {};
        }
    }

    // ============================================
    // Helper Methods
    // ============================================

    escapeHtml(str) {
        if (!str) return '';
        return str.replace(/[&<>]/g, (m) => {
            if (m === '&') return '&amp;';
            if (m === '<') return '&lt;';
            if (m === '>') return '&gt;';
            return m;
        });
    }

    showToast(message, type) {
        const flashContainer = document.querySelector('.flash-container');
        if (flashContainer) {
            const toast = document.createElement('div');
            toast.className = `flash-message flash-${type}`;
            toast.innerHTML = `
                <div class="flash-icon">
                    <i class="fas fa-${type === 'success' ? 'check-circle' : 'exclamation-circle'}"></i>
                </div>
                <div class="flash-content">
                    <span>${this.escapeHtml(message)}</span>
                </div>
                <button class="flash-close">&times;</button>
                <div class="flash-progress"></div>
            `;
            flashContainer.appendChild(toast);
            
            setTimeout(() => {
                toast.style.animation = 'slideOut 0.5s ease forwards';
                setTimeout(() => toast.remove(), 500);
            }, 5000);
            
            toast.querySelector('.flash-close').addEventListener('click', () => {
                toast.style.animation = 'slideOut 0.3s ease forwards';
                setTimeout(() => toast.remove(), 300);
            });
        }
    }

    destroy() {
        if (this.calendar) {
            this.calendar.destroy();
            this.calendar = null;
        }
    }
}

// ============================================
// Initialize Calendar
// ============================================

let calendarManager = null;

document.addEventListener('DOMContentLoaded', () => {
    const calendarElement = document.getElementById('calendar');
    if (calendarElement) {
        calendarManager = new CalendarManager({
            calendarElement: 'calendar',
            defaultView: 'dayGridMonth',
            onEventClick: (event) => {
                console.log('Event clicked:', event.title);
            },
            onDateClick: (date) => {
                console.log('Date clicked:', date);
            }
        });
    }
});

// ============================================
// Global Functions for HTML Event Handlers
// ============================================

window.changeCalendarView = (view) => calendarManager?.changeView(view);
window.prevCalendar = () => calendarManager?.prev();
window.nextCalendar = () => calendarManager?.next();
window.todayCalendar = () => calendarManager?.today();
window.refreshCalendar = () => calendarManager?.refreshEvents();
window.exportToICal = () => calendarManager?.exportToICal();
window.closeEventModal = () => {
    const modal = document.getElementById('eventModal');
    if (modal) modal.classList.remove('active');
};