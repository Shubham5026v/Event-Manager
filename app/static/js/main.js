/**
 * EventX - Futuristic Event Management Platform
 * Main JavaScript File v2.0
 * Interactive Features | Animations | WebSocket | Real-time Updates
 */

// ============================================
// Global Variables & Configuration
// ============================================
const CONFIG = {
    // API Endpoints
    API_BASE: '/api',
    WS_BASE: window.location.protocol === 'https:' ? 'wss://' : 'ws://',
    
    // Animation Settings
    ANIMATION_DURATION: 300,
    ANIMATION_DELAY: 100,
    
    // Auto-refresh Settings
    AUTO_REFRESH_INTERVAL: 30000, // 30 seconds
    SCORE_REFRESH_INTERVAL: 5000, // 5 seconds
    
    // Toast Settings
    TOAST_DURATION: 5000,
    
    // Debounce Settings
    DEBOUNCE_DELAY: 300
};

// Global State
let wsConnections = {};
let autoRefreshIntervals = {};
let currentUser = null;
let activeEventId = null;
let eventListeners = {};

// ============================================
// DOM Ready Event
// ============================================
document.addEventListener('DOMContentLoaded', () => {
    console.log('EventX Platform Initialized');
    initializeApp();
});

// ============================================
// Core Initialization
// ============================================
function initializeApp() {
    initializeAnimations();
    initializeNavbar();
    initializeFlashMessages();
    initializeForms();
    initializeTooltips();
    initializeKeyboardShortcuts();
    setupGlobalEventListeners();
    loadCurrentUser();
    
    // Initialize AOS if available
    if (typeof AOS !== 'undefined') {
        AOS.init({
            duration: 1000,
            once: true,
            offset: 100,
            easing: 'ease-out-cubic'
        });
    }
}

// ============================================
// Animation System
// ============================================
function initializeAnimations() {
    // Animate elements on scroll with Intersection Observer
    const animatedElements = document.querySelectorAll('[data-animate]');
    
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };
    
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const element = entry.target;
                const animation = element.dataset.animate || 'fadeInUp';
                const delay = element.dataset.delay || 0;
                
                setTimeout(() => {
                    element.classList.add(animation);
                    element.style.opacity = '1';
                }, delay);
                
                observer.unobserve(element);
            }
        });
    }, observerOptions);
    
    animatedElements.forEach(el => {
        el.style.opacity = '0';
        observer.observe(el);
    });
    
    // Add hover animations to cards
    document.querySelectorAll('.glass-card, .team-card, .event-card').forEach(card => {
        card.addEventListener('mouseenter', () => {
            card.style.transform = 'translateY(-5px)';
        });
        
        card.addEventListener('mouseleave', () => {
            card.style.transform = 'translateY(0)';
        });
    });
}

// ============================================
// Navbar & Mobile Menu
// ============================================
function initializeNavbar() {
    const menuToggle = document.querySelector('.menu-toggle');
    const navLinks = document.querySelector('.nav-links');
    const navbar = document.querySelector('.nav-holographic');
    
    // Mobile menu toggle
    if (menuToggle) {
        menuToggle.addEventListener('click', () => {
            menuToggle.classList.toggle('active');
            if (navLinks) navLinks.classList.toggle('active');
        });
    }
    
    // Close mobile menu on link click
    if (navLinks) {
        navLinks.querySelectorAll('a').forEach(link => {
            link.addEventListener('click', () => {
                if (menuToggle) menuToggle.classList.remove('active');
                navLinks.classList.remove('active');
            });
        });
    }
    
    // Navbar scroll effect
    let lastScroll = 0;
    window.addEventListener('scroll', () => {
        const currentScroll = window.pageYOffset;
        
        if (currentScroll > 100) {
            navbar?.classList.add('nav-scrolled');
        } else {
            navbar?.classList.remove('nav-scrolled');
        }
        
        lastScroll = currentScroll;
    });
    
    // Dropdown menus
    document.querySelectorAll('.nav-dropdown').forEach(dropdown => {
        const trigger = dropdown.querySelector('.user-menu, .dropdown-trigger');
        
        if (trigger) {
            trigger.addEventListener('click', (e) => {
                e.stopPropagation();
                dropdown.classList.toggle('active');
            });
        }
    });
    
    // Close dropdowns on click outside
    document.addEventListener('click', () => {
        document.querySelectorAll('.nav-dropdown.active').forEach(dropdown => {
            dropdown.classList.remove('active');
        });
    });
}

// ============================================
// Flash Messages System
// ============================================
function initializeFlashMessages() {
    const flashMessages = document.querySelectorAll('.flash-message');
    
    flashMessages.forEach(msg => {
        const closeBtn = msg.querySelector('.flash-close');
        const progress = msg.querySelector('.flash-progress');
        
        // Auto-close timer
        setTimeout(() => {
            closeFlashMessage(msg);
        }, CONFIG.TOAST_DURATION);
        
        // Close button handler
        if (closeBtn) {
            closeBtn.addEventListener('click', () => {
                closeFlashMessage(msg);
            });
        }
        
        // Progress bar animation
        if (progress) {
            progress.style.animation = `shrink ${CONFIG.TOAST_DURATION / 1000}s linear forwards`;
        }
        
        // Pause on hover
        msg.addEventListener('mouseenter', () => {
            if (progress) progress.style.animationPlayState = 'paused';
        });
        
        msg.addEventListener('mouseleave', () => {
            if (progress) progress.style.animationPlayState = 'running';
        });
    });
}

function closeFlashMessage(element) {
    element.style.animation = 'slideOut 0.3s ease forwards';
    setTimeout(() => {
        element.remove();
    }, 300);
}

// ============================================
// Toast Notification System
// ============================================
function showToast(message, type = 'info', duration = CONFIG.TOAST_DURATION) {
    const flashContainer = document.querySelector('.flash-container');
    if (!flashContainer) return;
    
    const toast = document.createElement('div');
    toast.className = `flash-message flash-${type}`;
    toast.innerHTML = `
        <div class="flash-icon">
            <i class="fas fa-${getToastIcon(type)}"></i>
        </div>
        <div class="flash-content">
            <span>${escapeHtml(message)}</span>
        </div>
        <button class="flash-close">&times;</button>
        <div class="flash-progress"></div>
    `;
    
    flashContainer.appendChild(toast);
    
    // Animate in
    toast.style.animation = 'slideIn 0.5s ease forwards';
    
    // Auto close
    setTimeout(() => {
        if (toast.parentNode) {
            closeFlashMessage(toast);
        }
    }, duration);
    
    // Close button handler
    const closeBtn = toast.querySelector('.flash-close');
    if (closeBtn) {
        closeBtn.addEventListener('click', () => {
            closeFlashMessage(toast);
        });
    }
    
    return toast;
}

function getToastIcon(type) {
    switch (type) {
        case 'success': return 'check-circle';
        case 'danger': return 'exclamation-triangle';
        case 'warning': return 'exclamation-triangle';
        case 'info': return 'info-circle';
        default: return 'bell';
    }
}

// ============================================
// Form Handling & Validation
// ============================================
function initializeForms() {
    // Form submission with loading state
    document.querySelectorAll('form').forEach(form => {
        form.addEventListener('submit', async (e) => {
            const submitBtn = form.querySelector('[type="submit"]');
            const originalText = submitBtn?.innerHTML;
            
            if (submitBtn && !form.classList.contains('no-loader')) {
                e.preventDefault();
                submitBtn.disabled = true;
                submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...';
                
                try {
                    await handleFormSubmit(form);
                } finally {
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = originalText;
                }
            }
        });
        
        // Real-time validation
        form.querySelectorAll('input, select, textarea').forEach(input => {
            input.addEventListener('blur', () => validateField(input));
            input.addEventListener('input', () => {
                if (input.classList.contains('error')) {
                    validateField(input);
                }
            });
        });
    });
}

async function handleFormSubmit(form) {
    const formData = new FormData(form);
    const action = form.action || window.location.href;
    const method = form.method || 'POST';
    
    // Validate form
    if (!validateForm(form)) {
        showToast('Please fix validation errors', 'warning');
        return;
    }
    
    try {
        const response = await fetch(action, {
            method: method,
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            }
        });
        
        if (response.ok) {
            const data = await response.json();
            showToast(data.message || 'Form submitted successfully', 'success');
            
            // Trigger custom event
            const event = new CustomEvent('form:success', { detail: { form, data } });
            document.dispatchEvent(event);
            
            // Optional redirect
            if (data.redirect) {
                setTimeout(() => {
                    window.location.href = data.redirect;
                }, 1000);
            }
        } else {
            throw new Error('Form submission failed');
        }
    } catch (error) {
        console.error('Form submission error:', error);
        showToast('An error occurred. Please try again.', 'danger');
    }
}

function validateForm(form) {
    let isValid = true;
    form.querySelectorAll('input, select, textarea').forEach(input => {
        if (!validateField(input)) isValid = false;
    });
    return isValid;
}

function validateField(input) {
    const value = input.value.trim();
    let isValid = true;
    let errorMessage = '';
    
    // Required validation
    if (input.hasAttribute('required') && !value) {
        isValid = false;
        errorMessage = 'This field is required';
    }
    
    // Email validation
    if (input.type === 'email' && value && !isValidEmail(value)) {
        isValid = false;
        errorMessage = 'Please enter a valid email address';
    }
    
    // Phone validation
    if (input.type === 'tel' && value && !isValidPhone(value)) {
        isValid = false;
        errorMessage = 'Please enter a valid phone number';
    }
    
    // URL validation
    if (input.type === 'url' && value && !isValidUrl(value)) {
        isValid = false;
        errorMessage = 'Please enter a valid URL';
    }
    
    // Min length validation
    const minLength = input.getAttribute('minlength');
    if (minLength && value.length < parseInt(minLength)) {
        isValid = false;
        errorMessage = `Minimum ${minLength} characters required`;
    }
    
    // Max length validation
    const maxLength = input.getAttribute('maxlength');
    if (maxLength && value.length > parseInt(maxLength)) {
        isValid = false;
        errorMessage = `Maximum ${maxLength} characters allowed`;
    }
    
    // Show/hide error
    const errorElement = input.parentElement?.querySelector('.error-message');
    if (!isValid && errorMessage) {
        input.classList.add('error');
        if (errorElement) {
            errorElement.textContent = errorMessage;
            errorElement.style.display = 'block';
        } else {
            const newError = document.createElement('div');
            newError.className = 'error-message';
            newError.textContent = errorMessage;
            input.parentElement?.appendChild(newError);
        }
    } else {
        input.classList.remove('error');
        if (errorElement) {
            errorElement.style.display = 'none';
        }
    }
    
    return isValid;
}

function isValidEmail(email) {
    return /^[^\s@]+@([^\s@]+\.)+[^\s@]+$/.test(email);
}

function isValidPhone(phone) {
    return /^[\d\s\-+()]{10,}$/.test(phone);
}

function isValidUrl(url) {
    try {
        new URL(url);
        return true;
    } catch {
        return false;
    }
}

// ============================================
// Tooltip System
// ============================================
function initializeTooltips() {
    const tooltips = document.querySelectorAll('[data-tooltip]');
    
    tooltips.forEach(element => {
        let tooltipElement = null;
        
        element.addEventListener('mouseenter', (e) => {
            const text = element.dataset.tooltip;
            if (!text) return;
            
            tooltipElement = document.createElement('div');
            tooltipElement.className = 'tooltip';
            tooltipElement.textContent = text;
            tooltipElement.style.cssText = `
                position: absolute;
                background: var(--bg-glass-dark);
                backdrop-filter: blur(10px);
                color: white;
                padding: 0.3rem 0.8rem;
                border-radius: 8px;
                font-size: 0.75rem;
                border: 1px solid var(--border-glow);
                white-space: nowrap;
                z-index: 1000;
                pointer-events: none;
            `;
            
            document.body.appendChild(tooltipElement);
            
            const rect = element.getBoundingClientRect();
            tooltipElement.style.top = `${rect.top - tooltipElement.offsetHeight - 5}px`;
            tooltipElement.style.left = `${rect.left + (rect.width / 2) - (tooltipElement.offsetWidth / 2)}px`;
        });
        
        element.addEventListener('mouseleave', () => {
            if (tooltipElement) {
                tooltipElement.remove();
                tooltipElement = null;
            }
        });
    });
}

// ============================================
// Keyboard Shortcuts
// ============================================
function initializeKeyboardShortcuts() {
    document.addEventListener('keydown', (e) => {
        // Ctrl + S - Save
        if (e.ctrlKey && e.key === 's') {
            e.preventDefault();
            const saveBtn = document.querySelector('[data-shortcut="save"], .btn-save, .btn-primary-modal');
            if (saveBtn) saveBtn.click();
        }
        
        // Ctrl + F - Search
        if (e.ctrlKey && e.key === 'f') {
            e.preventDefault();
            const searchInput = document.querySelector('input[type="search"], #searchInput');
            if (searchInput) searchInput.focus();
        }
        
        // Escape - Close modals
        if (e.key === 'Escape') {
            document.querySelectorAll('.modal.active').forEach(modal => {
                const closeBtn = modal.querySelector('.modal-close');
                if (closeBtn) closeBtn.click();
            });
        }
        
        // Ctrl + R - Refresh data
        if (e.ctrlKey && e.key === 'r') {
            e.preventDefault();
            const refreshBtn = document.querySelector('[data-shortcut="refresh"], .btn-refresh');
            if (refreshBtn) refreshBtn.click();
            else location.reload();
        }
    });
}

// ============================================
// WebSocket Manager
// ============================================
class WebSocketManager {
    constructor(endpoint) {
        this.endpoint = endpoint;
        this.connection = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 3000;
        this.listeners = {};
    }
    
    connect() {
        const wsUrl = `${CONFIG.WS_BASE}${window.location.host}${this.endpoint}`;
        this.connection = new WebSocket(wsUrl);
        
        this.connection.onopen = () => {
            console.log(`WebSocket connected: ${this.endpoint}`);
            this.reconnectAttempts = 0;
            this.emit('connected', {});
        };
        
        this.connection.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.emit(data.type, data);
            } catch (error) {
                console.error('WebSocket message error:', error);
            }
        };
        
        this.connection.onclose = () => {
            console.log(`WebSocket disconnected: ${this.endpoint}`);
            this.emit('disconnected', {});
            this.reconnect();
        };
        
        this.connection.onerror = (error) => {
            console.error(`WebSocket error: ${this.endpoint}`, error);
            this.emit('error', error);
        };
    }
    
    reconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            console.log(`Reconnecting... Attempt ${this.reconnectAttempts}`);
            setTimeout(() => this.connect(), this.reconnectDelay);
        }
    }
    
    send(type, data) {
        if (this.connection && this.connection.readyState === WebSocket.OPEN) {
            this.connection.send(JSON.stringify({ type, ...data }));
        }
    }
    
    on(event, callback) {
        if (!this.listeners[event]) this.listeners[event] = [];
        this.listeners[event].push(callback);
    }
    
    emit(event, data) {
        if (this.listeners[event]) {
            this.listeners[event].forEach(callback => callback(data));
        }
    }
    
    disconnect() {
        if (this.connection) {
            this.connection.close();
        }
    }
}

// ============================================
// Real-time Score Updates
// ============================================
function initScoreboardWebSocket(eventId) {
    if (wsConnections[eventId]) {
        wsConnections[eventId].disconnect();
    }
    
    const ws = new WebSocketManager(`/ws/scoreboard/${eventId}`);
    ws.connect();
    
    ws.on('score_update', (data) => {
        updateTeamScore(data.teamId, data.score);
    });
    
    ws.on('leaderboard_update', (data) => {
        updateLeaderboard(data.leaderboard);
    });
    
    wsConnections[eventId] = ws;
    return ws;
}

function updateTeamScore(teamId, newScore) {
    const scoreElement = document.getElementById(`score-${teamId}`);
    const oldScore = parseFloat(scoreElement?.textContent || 0);
    const change = newScore - oldScore;
    
    if (scoreElement) {
        scoreElement.textContent = newScore.toFixed(1);
        scoreElement.classList.add('score-updated');
        setTimeout(() => scoreElement.classList.remove('score-updated'), 500);
        
        // Show score change indicator
        if (Math.abs(change) > 0.01) {
            showScoreChange(teamId, change);
        }
    }
    
    // Update row highlighting
    const row = document.getElementById(`team-row-${teamId}`);
    if (row) {
        row.classList.add('score-updated');
        setTimeout(() => row.classList.remove('score-updated'), 1000);
    }
}

function showScoreChange(teamId, change) {
    const row = document.getElementById(`team-row-${teamId}`);
    if (!row) return;
    
    const changeElement = document.createElement('span');
    changeElement.className = `score-change ${change > 0 ? 'positive' : 'negative'}`;
    changeElement.textContent = `${change > 0 ? '+' : ''}${change.toFixed(1)}`;
    
    const scoreCell = row.querySelector('.score-cell');
    if (scoreCell) {
        scoreCell.appendChild(changeElement);
        setTimeout(() => changeElement.remove(), 1000);
    }
}

function updateLeaderboard(leaderboard) {
    const tbody = document.querySelector('.leaderboard-table tbody');
    if (!tbody) return;
    
    leaderboard.forEach((team, index) => {
        const row = document.getElementById(`team-row-${team.id}`);
        if (row) {
            const rankCell = row.querySelector('.rank-cell');
            const scoreCell = row.querySelector('.score-cell');
            
            if (rankCell) {
                rankCell.innerHTML = getRankIcon(index);
            }
            if (scoreCell) {
                const oldScore = parseFloat(scoreCell.textContent);
                const newScore = team.score;
                if (Math.abs(newScore - oldScore) > 0.01) {
                    showScoreChange(team.id, newScore - oldScore);
                }
                scoreCell.innerHTML = `${newScore.toFixed(1)}`;
            }
            
            // Update progress bar
            const progressBar = row.querySelector('.progress-bar');
            if (progressBar) {
                progressBar.style.width = `${(team.score / 100) * 100}%`;
            }
        }
    });
}

function getRankIcon(index) {
    if (index === 0) return '🥇';
    if (index === 1) return '🥈';
    if (index === 2) return '🥉';
    return `#${index + 1}`;
}

// ============================================
// Auto-refresh System
// ============================================
function startAutoRefresh(endpoint, interval, callback) {
    if (autoRefreshIntervals[endpoint]) {
        clearInterval(autoRefreshIntervals[endpoint]);
    }
    
    autoRefreshIntervals[endpoint] = setInterval(async () => {
        try {
            const response = await fetch(`${CONFIG.API_BASE}${endpoint}`);
            const data = await response.json();
            if (callback) callback(data);
        } catch (error) {
            console.error(`Auto-refresh error for ${endpoint}:`, error);
        }
    }, interval);
}

function stopAutoRefresh(endpoint) {
    if (autoRefreshIntervals[endpoint]) {
        clearInterval(autoRefreshIntervals[endpoint]);
        delete autoRefreshIntervals[endpoint];
    }
}

// ============================================
// Particle System
// ============================================
function initParticleSystem() {
    const particleField = document.getElementById('particleField');
    if (!particleField) return;
    
    const particleCount = window.innerWidth < 768 ? 50 : 100;
    
    for (let i = 0; i < particleCount; i++) {
        const particle = document.createElement('div');
        particle.className = 'particle';
        particle.style.left = Math.random() * 100 + '%';
        particle.style.top = Math.random() * 100 + '%';
        particle.style.animationDelay = Math.random() * 20 + 's';
        particle.style.animationDuration = 10 + Math.random() * 20 + 's';
        particleField.appendChild(particle);
    }
}

// ============================================
// Mouse Parallax Effect
// ============================================
function initParallax() {
    const orbs = document.querySelectorAll('.glow-orb');
    
    document.addEventListener('mousemove', (e) => {
        const mouseX = e.clientX / window.innerWidth;
        const mouseY = e.clientY / window.innerHeight;
        
        orbs.forEach((orb, index) => {
            const speed = 20 + index * 10;
            const x = (mouseX - 0.5) * speed;
            const y = (mouseY - 0.5) * speed;
            orb.style.transform = `translate(${x}px, ${y}px)`;
        });
    });
}

// ============================================
// Global Event Listeners
// ============================================
function setupGlobalEventListeners() {
    // Handle visibility change (tab focus)
    document.addEventListener('visibilitychange', () => {
        if (document.hidden) {
            // Pause auto-refresh when tab is hidden
            Object.keys(autoRefreshIntervals).forEach(endpoint => {
                // Optionally pause
            });
        } else {
            // Resume
            Object.keys(autoRefreshIntervals).forEach(endpoint => {
                // Optionally resume
            });
        }
    });
    
    // Handle online/offline status
    window.addEventListener('online', () => {
        showToast('Connection restored', 'success');
        location.reload();
    });
    
    window.addEventListener('offline', () => {
        showToast('Connection lost. Please check your internet.', 'warning');
    });
}

// ============================================
// User Management
// ============================================
async function loadCurrentUser() {
    try {
        const response = await fetch(`${CONFIG.API_BASE}/auth/me`);
        if (response.ok) {
            currentUser = await response.json();
            updateUIForUser(currentUser);
        }
    } catch (error) {
        console.error('Error loading user:', error);
    }
}

function updateUIForUser(user) {
    // Update user avatar and name
    const userMenu = document.querySelector('.user-menu span');
    if (userMenu && user.username) {
        userMenu.textContent = user.username;
    }
    
    // Show/hide admin elements
    const adminElements = document.querySelectorAll('[data-role="admin"]');
    adminElements.forEach(el => {
        el.style.display = user.role === 'admin' ? 'flex' : 'none';
    });
    
    const judgeElements = document.querySelectorAll('[data-role="judge"]');
    judgeElements.forEach(el => {
        el.style.display = user.role === 'judge' ? 'flex' : 'none';
    });
}

// ============================================
// Utility Functions
// ============================================
function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function debounce(func, delay = CONFIG.DEBOUNCE_DELAY) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, delay);
    };
}

function throttle(func, limit) {
    let inThrottle;
    return function(...args) {
        if (!inThrottle) {
            func.apply(this, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}

function formatDate(date, format = 'short') {
    const d = new Date(date);
    if (format === 'short') {
        return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    } else if (format === 'long') {
        return d.toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });
    } else if (format === 'time') {
        return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
    }
    return d.toLocaleString();
}

function formatNumber(num, decimals = 0) {
    return num.toLocaleString(undefined, { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

// ============================================
// Export Functions for Global Access
// ============================================
window.EventX = {
    showToast,
    initParticleSystem,
    initParallax,
    WebSocketManager,
    startAutoRefresh,
    stopAutoRefresh,
    formatDate,
    formatNumber,
    escapeHtml,
    debounce,
    throttle
};

// Initialize background effects
initParticleSystem();
initParallax();