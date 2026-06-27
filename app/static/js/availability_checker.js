/**
 * EventX - Venue Availability Checker
 * Real-time availability checking with conflict detection and smart suggestions
 * Version 2.0
 */

class VenueAvailabilityChecker {
    constructor(options = {}) {
        this.apiEndpoint = options.apiEndpoint || '/bookings/api/check-availability';
        this.slotEndpoint = options.slotEndpoint || '/calendar/api/available-slots';
        this.alternativeEndpoint = options.alternativeEndpoint || '/venues/api/alternatives';
        this.debounceDelay = options.debounceDelay || 500;
        this.cacheDuration = options.cacheDuration || 30000; // 30 seconds
        this.cache = new Map();
        this.pendingRequests = new Map();
        
        // DOM Elements
        this.elements = {
            venueSelect: options.venueSelect || document.getElementById('venueSelect'),
            dateInput: options.dateInput || document.getElementById('bookingDate'),
            startTimeInput: options.startTimeInput || document.getElementById('startTime'),
            endTimeInput: options.endTimeInput || document.getElementById('endTime'),
            durationSelect: options.durationSelect || document.getElementById('durationSelect'),
            availabilityStatus: options.availabilityStatus || document.getElementById('availabilityStatus'),
            conflictWarning: options.conflictWarning || document.getElementById('conflictWarning'),
            alternativeVenues: options.alternativeVenues || document.getElementById('alternativeVenues'),
            alternativeTimes: options.alternativeTimes || document.getElementById('alternativeTimes'),
            timeSlotsContainer: options.timeSlotsContainer || document.getElementById('timeSlotsContainer')
        };
        
        this.init();
    }

    init() {
        this.bindEvents();
        this.setupDateTimePickers();
        this.loadInitialData();
    }

    bindEvents() {
        // Main availability check triggers
        if (this.elements.venueSelect) {
            this.elements.venueSelect.addEventListener('change', () => this.debouncedCheckAvailability());
        }
        if (this.elements.dateInput) {
            this.elements.dateInput.addEventListener('change', () => {
                this.debouncedCheckAvailability();
                this.loadTimeSlots();
            });
        }
        if (this.elements.startTimeInput) {
            this.elements.startTimeInput.addEventListener('change', () => {
                this.debouncedCheckAvailability();
                this.validateTimeRange();
            });
        }
        if (this.elements.endTimeInput) {
            this.elements.endTimeInput.addEventListener('change', () => {
                this.debouncedCheckAvailability();
                this.validateTimeRange();
            });
        }
        if (this.elements.durationSelect) {
            this.elements.durationSelect.addEventListener('change', () => this.loadTimeSlots());
        }
        
        // Real-time validation
        if (this.elements.startTimeInput && this.elements.endTimeInput) {
            this.elements.startTimeInput.addEventListener('blur', () => this.validateTimeRange());
            this.elements.endTimeInput.addEventListener('blur', () => this.validateTimeRange());
        }
    }

    setupDateTimePickers() {
        const today = new Date().toISOString().split('T')[0];
        const maxDate = new Date();
        maxDate.setDate(maxDate.getDate() + 90);
        
        if (this.elements.dateInput) {
            this.elements.dateInput.min = today;
            this.elements.dateInput.max = maxDate.toISOString().split('T')[0];
        }
        
        // Set default date if empty
        if (this.elements.dateInput && !this.elements.dateInput.value) {
            this.elements.dateInput.value = today;
        }
    }

    loadInitialData() {
        if (this.elements.dateInput && this.elements.dateInput.value) {
            this.loadTimeSlots();
        }
    }

    debouncedCheckAvailability() {
        clearTimeout(this.debounceTimeout);
        this.debounceTimeout = setTimeout(() => {
            this.checkAvailability();
        }, this.debounceDelay);
    }

    async checkAvailability() {
        const params = this.getAvailabilityParams();
        
        if (!this.isValidParams(params)) {
            this.updateAvailabilityStatus('incomplete', 'Please fill in all required fields');
            return;
        }
        
        if (!this.validateTimeRange()) {
            return;
        }
        
        this.updateAvailabilityStatus('loading', 'Checking availability...');
        
        try {
            const cacheKey = this.generateCacheKey(params);
            const cached = this.getFromCache(cacheKey);
            
            if (cached) {
                this.processAvailabilityResult(cached);
                return;
            }
            
            const requestKey = this.getRequestKey(params);
            if (this.pendingRequests.has(requestKey)) {
                this.pendingRequests.get(requestKey).abort();
            }
            
            const controller = new AbortController();
            this.pendingRequests.set(requestKey, controller);
            
            const response = await fetch(this.apiEndpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify(params),
                signal: controller.signal
            });
            
            this.pendingRequests.delete(requestKey);
            
            if (!response.ok) {
                throw new Error('Failed to check availability');
            }
            
            const data = await response.json();
            this.saveToCache(cacheKey, data);
            this.processAvailabilityResult(data);
            
        } catch (error) {
            if (error.name === 'AbortError') {
                console.log('Request aborted');
                return;
            }
            console.error('Availability check error:', error);
            this.updateAvailabilityStatus('error', 'Failed to check availability. Please try again.');
        }
    }

    processAvailabilityResult(data) {
        if (data.available) {
            this.updateAvailabilityStatus('available', '✓ Venue is available for the selected time slot!', 'success');
            this.clearConflicts();
            this.showAlternativeTimes(data.alternative_times);
        } else {
            this.updateAvailabilityStatus('unavailable', '✗ Venue is not available for the selected time slot', 'error');
            this.showConflicts(data.conflicts);
            this.showAlternativeVenues(data.alternative_venues);
            this.showAlternativeTimes(data.alternative_times);
        }
    }

    async loadTimeSlots() {
        if (!this.elements.timeSlotsContainer || !this.elements.dateInput) return;
        
        const date = this.elements.dateInput.value;
        const venueId = this.elements.venueSelect ? this.elements.venueSelect.value : null;
        const duration = this.elements.durationSelect ? this.elements.durationSelect.value : 60;
        
        if (!date || !venueId) {
            this.elements.timeSlotsContainer.innerHTML = '<div class="empty-state">Select venue and date to see available slots</div>';
            return;
        }
        
        this.elements.timeSlotsContainer.innerHTML = '<div class="loading-spinner"><i class="fas fa-spinner fa-spin"></i> Loading time slots...</div>';
        
        try {
            const url = `${this.slotEndpoint}?venue_id=${venueId}&date=${date}&duration=${duration}`;
            const response = await fetch(url);
            const data = await response.json();
            
            this.renderTimeSlots(data.slots);
        } catch (error) {
            console.error('Error loading time slots:', error);
            this.elements.timeSlotsContainer.innerHTML = '<div class="error-message">Failed to load time slots</div>';
        }
    }

    renderTimeSlots(slots) {
        if (!this.elements.timeSlotsContainer) return;
        
        if (!slots || slots.length === 0) {
            this.elements.timeSlotsContainer.innerHTML = '<div class="empty-state">No available time slots for this date</div>';
            return;
        }
        
        const grid = document.createElement('div');
        grid.className = 'time-slots-grid';
        
        slots.forEach(slot => {
            const slotBtn = document.createElement('button');
            slotBtn.className = `time-slot ${slot.available ? 'available' : 'booked'}`;
            slotBtn.textContent = `${slot.start_time} - ${slot.end_time}`;
            slotBtn.disabled = !slot.available;
            
            if (slot.available) {
                slotBtn.addEventListener('click', () => this.selectTimeSlot(slot.start_time, slot.end_time));
            }
            
            grid.appendChild(slotBtn);
        });
        
        this.elements.timeSlotsContainer.innerHTML = '';
        this.elements.timeSlotsContainer.appendChild(grid);
    }

    selectTimeSlot(startTime, endTime) {
        if (this.elements.startTimeInput) {
            this.elements.startTimeInput.value = startTime;
        }
        if (this.elements.endTimeInput) {
            this.elements.endTimeInput.value = endTime;
        }
        this.checkAvailability();
        
        // Scroll to availability status
        if (this.elements.availabilityStatus) {
            this.elements.availabilityStatus.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
    }

    validateTimeRange() {
        if (!this.elements.startTimeInput || !this.elements.endTimeInput) return true;
        
        const startTime = this.elements.startTimeInput.value;
        const endTime = this.elements.endTimeInput.value;
        
        if (startTime && endTime && startTime >= endTime) {
            this.updateAvailabilityStatus('invalid', 'End time must be after start time', 'warning');
            return false;
        }
        
        return true;
    }

    showConflicts(conflicts) {
        if (!this.elements.conflictWarning) return;
        
        if (!conflicts || conflicts.length === 0) {
            this.elements.conflictWarning.innerHTML = '';
            return;
        }
        
        const conflictHtml = `
            <div class="conflict-warning glass-card">
                <div class="conflict-header">
                    <i class="fas fa-exclamation-triangle"></i>
                    <strong>Conflicting Bookings:</strong>
                </div>
                <ul class="conflict-list">
                    ${conflicts.map(conflict => `
                        <li>
                            <strong>${this.escapeHtml(conflict.title)}</strong><br>
                            <small>${conflict.start_time} - ${conflict.end_time}</small><br>
                            <small class="conflict-status">Status: ${conflict.status}</small>
                        </li>
                    `).join('')}
                </ul>
            </div>
        `;
        
        this.elements.conflictWarning.innerHTML = conflictHtml;
    }

    showAlternativeVenues(venues) {
        if (!this.elements.alternativeVenues) return;
        
        if (!venues || venues.length === 0) {
            this.elements.alternativeVenues.innerHTML = '';
            return;
        }
        
        const venuesHtml = `
            <div class="alternative-venues glass-card">
                <div class="alternative-header">
                    <i class="fas fa-building"></i>
                    <strong>Alternative Venues Available:</strong>
                </div>
                <div class="venues-list">
                    ${venues.map(venue => `
                        <div class="alternative-venue" data-venue-id="${venue.id}">
                            <div class="venue-info">
                                <span class="venue-name">${this.escapeHtml(venue.name)}</span>
                                <span class="venue-type">${venue.type}</span>
                                <span class="venue-capacity">Capacity: ${venue.capacity}</span>
                            </div>
                            <button class="btn-select-venue" onclick="window.availabilityChecker.selectAlternativeVenue(${venue.id})">
                                Select
                            </button>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
        
        this.elements.alternativeVenues.innerHTML = venuesHtml;
    }

    showAlternativeTimes(times) {
        if (!this.elements.alternativeTimes) return;
        
        if (!times || times.length === 0) {
            this.elements.alternativeTimes.innerHTML = '';
            return;
        }
        
        const timesHtml = `
            <div class="alternative-times glass-card">
                <div class="alternative-header">
                    <i class="fas fa-clock"></i>
                    <strong>Alternative Time Slots:</strong>
                </div>
                <div class="times-list">
                    ${times.map(time => `
                        <button class="alternative-time" onclick="window.availabilityChecker.selectAlternativeTime('${time.start_time}', '${time.end_time}')">
                            ${time.start_time} - ${time.end_time}
                            ${time.venue_name ? `<small>(${this.escapeHtml(time.venue_name)})</small>` : ''}
                        </button>
                    `).join('')}
                </div>
            </div>
        `;
        
        this.elements.alternativeTimes.innerHTML = timesHtml;
    }

    selectAlternativeVenue(venueId) {
        if (this.elements.venueSelect) {
            this.elements.venueSelect.value = venueId;
            this.elements.venueSelect.dispatchEvent(new Event('change'));
            this.loadTimeSlots();
        }
    }

    selectAlternativeTime(startTime, endTime) {
        if (this.elements.startTimeInput) {
            this.elements.startTimeInput.value = startTime;
        }
        if (this.elements.endTimeInput) {
            this.elements.endTimeInput.value = endTime;
        }
        this.checkAvailability();
    }

    clearConflicts() {
        if (this.elements.conflictWarning) {
            this.elements.conflictWarning.innerHTML = '';
        }
        if (this.elements.alternativeVenues) {
            this.elements.alternativeVenues.innerHTML = '';
        }
        if (this.elements.alternativeTimes) {
            this.elements.alternativeTimes.innerHTML = '';
        }
    }

    updateAvailabilityStatus(status, message, type = 'info') {
        if (!this.elements.availabilityStatus) return;
        
        let icon = '';
        let className = '';
        
        switch (status) {
            case 'available':
                icon = '<i class="fas fa-check-circle"></i>';
                className = 'status-available';
                break;
            case 'unavailable':
                icon = '<i class="fas fa-times-circle"></i>';
                className = 'status-unavailable';
                break;
            case 'loading':
                icon = '<i class="fas fa-spinner fa-spin"></i>';
                className = 'status-loading';
                break;
            case 'error':
                icon = '<i class="fas fa-exclamation-circle"></i>';
                className = 'status-error';
                break;
            case 'warning':
                icon = '<i class="fas fa-exclamation-triangle"></i>';
                className = 'status-warning';
                break;
            default:
                icon = '<i class="fas fa-info-circle"></i>';
                className = 'status-info';
        }
        
        this.elements.availabilityStatus.innerHTML = `
            <div class="availability-status ${className}">
                ${icon}
                <span>${this.escapeHtml(message)}</span>
            </div>
        `;
    }

    getAvailabilityParams() {
        return {
            venue_id: this.elements.venueSelect ? parseInt(this.elements.venueSelect.value) : null,
            date: this.elements.dateInput ? this.elements.dateInput.value : null,
            start_time: this.elements.startTimeInput ? this.elements.startTimeInput.value : null,
            end_time: this.elements.endTimeInput ? this.elements.endTimeInput.value : null
        };
    }

    isValidParams(params) {
        return params.venue_id && params.date && params.start_time && params.end_time;
    }

    generateCacheKey(params) {
        return `${params.venue_id}_${params.date}_${params.start_time}_${params.end_time}`;
    }

    getRequestKey(params) {
        return `${params.venue_id}_${params.date}_${params.start_time}_${params.end_time}`;
    }

    getFromCache(key) {
        const cached = this.cache.get(key);
        if (cached && Date.now() - cached.timestamp < this.cacheDuration) {
            return cached.data;
        }
        return null;
    }

    saveToCache(key, data) {
        this.cache.set(key, {
            data: data,
            timestamp: Date.now()
        });
    }

    clearCache() {
        this.cache.clear();
    }

    escapeHtml(str) {
        if (!str) return '';
        return str.replace(/[&<>]/g, function(m) {
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
        clearTimeout(this.debounceTimeout);
        this.cache.clear();
        this.pendingRequests.forEach(controller => controller.abort());
        this.pendingRequests.clear();
    }
}

// ============================================
// Initialize Availability Checker
// ============================================

let availabilityChecker = null;

document.addEventListener('DOMContentLoaded', () => {
    availabilityChecker = new VenueAvailabilityChecker();
});

// ============================================
// Global Functions for HTML Event Handlers
// ============================================

window.checkAvailability = () => availabilityChecker?.checkAvailability();
window.loadTimeSlots = () => availabilityChecker?.loadTimeSlots();
window.selectTimeSlot = (start, end) => availabilityChecker?.selectTimeSlot(start, end);
window.selectAlternativeVenue = (venueId) => availabilityChecker?.selectAlternativeVenue(venueId);
window.selectAlternativeTime = (start, end) => availabilityChecker?.selectAlternativeTime(start, end);