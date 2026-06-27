/**
 * EventX - Approval Workflow Manager
 * Handles multi-level approval workflow (Faculty → Admin → Security)
 * Version 2.0
 */

class ApprovalWorkflowManager {
    constructor(options = {}) {
        this.apiEndpoint = options.apiEndpoint || '/approvals/api';
        this.wsEndpoint = options.wsEndpoint || '/ws/approvals';
        this.pollInterval = options.pollInterval || 30000;
        this.autoRefresh = options.autoRefresh !== false;
        
        // DOM Elements
        this.elements = {
            approvalContainer: options.approvalContainer || document.getElementById('approvalsGrid'),
            approvalStats: options.approvalStats || document.getElementById('approvalStats'),
            approvalTimeline: options.approvalTimeline || document.getElementById('approvalTimeline'),
            approveBtn: options.approveBtn || null,
            rejectBtn: options.rejectBtn || null,
            commentsInput: options.commentsInput || null,
            notificationBadge: options.notificationBadge || document.getElementById('approvalNotificationBadge'),
            filterSelect: options.filterSelect || document.getElementById('stageFilter'),
            searchInput: options.searchInput || document.getElementById('searchInput')
        };
        
        // State
        this.wsConnection = null;
        this.pollTimer = null;
        this.pendingApprovals = [];
        this.currentApproval = null;
        this.currentFilters = {
            stage: 'all',
            priority: 'all',
            search: ''
        };
        this.listeners = new Map();
        
        this.init();
    }

    init() {
        this.bindEvents();
        this.connectWebSocket();
        this.startAutoRefresh();
        this.loadPendingApprovals();
        this.updateNotificationBadge();
        this.initFilters();
    }

    bindEvents() {
        // Approval action buttons
        if (this.elements.approveBtn) {
            this.elements.approveBtn.addEventListener('click', () => this.approveBooking());
        }
        if (this.elements.rejectBtn) {
            this.elements.rejectBtn.addEventListener('click', () => this.rejectBooking());
        }
        
        // Filter events
        if (this.elements.filterSelect) {
            this.elements.filterSelect.addEventListener('change', () => this.applyFilters());
        }
        if (this.elements.searchInput) {
            this.elements.searchInput.addEventListener('keyup', () => this.applyFilters());
        }
        
        // Priority filter
        const priorityFilter = document.getElementById('priorityFilter');
        if (priorityFilter) {
            priorityFilter.addEventListener('change', () => this.applyFilters());
        }
        
        // Batch actions
        const batchApproveBtn = document.getElementById('batchApproveBtn');
        const batchRejectBtn = document.getElementById('batchRejectBtn');
        const selectAllCheckbox = document.getElementById('selectAllCheckbox');
        
        if (batchApproveBtn) batchApproveBtn.addEventListener('click', () => this.batchApprove());
        if (batchRejectBtn) batchRejectBtn.addEventListener('click', () => this.batchReject());
        if (selectAllCheckbox) selectAllCheckbox.addEventListener('change', () => this.toggleSelectAll());
        
        // ESC key to close modals
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.closeModal();
            }
        });
        
        // Page visibility - pause/resume polling
        document.addEventListener('visibilitychange', () => {
            if (document.hidden) {
                this.stopAutoRefresh();
            } else {
                this.startAutoRefresh();
                this.loadPendingApprovals();
            }
        });
    }

    initFilters() {
        this.applyFilters();
    }

    applyFilters() {
        const stage = this.elements.filterSelect ? this.elements.filterSelect.value : 'all';
        const priority = document.getElementById('priorityFilter') ? document.getElementById('priorityFilter').value : 'all';
        const search = this.elements.searchInput ? this.elements.searchInput.value.toLowerCase() : '';
        
        this.currentFilters = { stage, priority, search };
        this.renderApprovals();
    }

    connectWebSocket() {
        if (!window.WebSocket) {
            console.warn('WebSocket not supported, falling back to polling');
            return;
        }
        
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}${this.wsEndpoint}`;
        
        try {
            this.wsConnection = new WebSocket(wsUrl);
            
            this.wsConnection.onopen = () => {
                console.log('Approval WebSocket connected');
                this.subscribeToApprovals();
            };
            
            this.wsConnection.onmessage = (event) => {
                const data = JSON.parse(event.data);
                this.handleWebSocketMessage(data);
            };
            
            this.wsConnection.onerror = (error) => {
                console.error('WebSocket error:', error);
            };
            
            this.wsConnection.onclose = () => {
                console.log('WebSocket disconnected, reconnecting in 5 seconds...');
                setTimeout(() => this.connectWebSocket(), 5000);
            };
        } catch (error) {
            console.error('WebSocket connection failed:', error);
        }
    }

    subscribeToApprovals() {
        if (this.wsConnection && this.wsConnection.readyState === WebSocket.OPEN) {
            this.wsConnection.send(JSON.stringify({
                type: 'subscribe',
                resource: 'approvals'
            }));
        }
    }

    handleWebSocketMessage(data) {
        switch (data.type) {
            case 'new_approval':
                this.onNewApproval(data.approval);
                break;
            case 'approval_updated':
                this.onApprovalUpdated(data.approval);
                break;
            case 'approval_completed':
                this.onApprovalCompleted(data.approval);
                break;
            case 'batch_update':
                this.onBatchUpdate(data.updates);
                break;
            default:
                console.log('Unknown message type:', data.type);
        }
    }

    onNewApproval(approval) {
        this.pendingApprovals.unshift(approval);
        this.renderApprovals();
        this.updateStats();
        this.updateNotificationBadge();
        this.showNotification('New approval request received', 'info');
        this.emit('new_approval', approval);
        
        // Play notification sound if enabled
        this.playNotificationSound();
    }

    onApprovalUpdated(approval) {
        const index = this.pendingApprovals.findIndex(a => a.id === approval.id);
        if (index !== -1) {
            this.pendingApprovals[index] = approval;
            this.renderApprovals();
        }
        this.updateStats();
        this.updateNotificationBadge();
        this.emit('approval_updated', approval);
    }

    onApprovalCompleted(approval) {
        this.pendingApprovals = this.pendingApprovals.filter(a => a.id !== approval.id);
        this.renderApprovals();
        this.updateStats();
        this.updateNotificationBadge();
        this.showNotification(`Approval completed for ${approval.booking_title}`, 'success');
        this.emit('approval_completed', approval);
    }

    onBatchUpdate(updates) {
        updates.forEach(update => {
            if (update.action === 'added') {
                this.onNewApproval(update.approval);
            } else if (update.action === 'updated') {
                this.onApprovalUpdated(update.approval);
            } else if (update.action === 'removed') {
                this.pendingApprovals = this.pendingApprovals.filter(a => a.id !== update.approval_id);
            }
        });
        this.renderApprovals();
        this.updateStats();
        this.updateNotificationBadge();
    }

    async loadPendingApprovals() {
        try {
            const response = await fetch(`${this.apiEndpoint}/pending`, {
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            });
            
            if (!response.ok) throw new Error('Failed to load approvals');
            
            const data = await response.json();
            this.pendingApprovals = data.approvals || [];
            this.renderApprovals();
            this.updateStats();
            this.updateNotificationBadge();
            this.emit('approvals_loaded', this.pendingApprovals);
        } catch (error) {
            console.error('Error loading approvals:', error);
            this.showError('Failed to load pending approvals');
        }
    }

    renderApprovals() {
        if (!this.elements.approvalContainer) return;
        
        let filteredApprovals = this.filterApprovals(this.pendingApprovals);
        filteredApprovals = this.sortApprovals(filteredApprovals);
        
        if (filteredApprovals.length === 0) {
            this.elements.approvalContainer.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-check-circle"></i>
                    <h3>All Caught Up!</h3>
                    <p>No pending approvals match your criteria.</p>
                </div>
            `;
            return;
        }
        
        this.elements.approvalContainer.innerHTML = filteredApprovals.map(approval => this.renderApprovalCard(approval)).join('');
        
        // Re-attach event listeners for dynamically created elements
        this.attachCardEventListeners();
    }

    filterApprovals(approvals) {
        return approvals.filter(approval => {
            if (this.currentFilters.stage !== 'all' && approval.stage !== this.currentFilters.stage) return false;
            
            const priority = approval.booking?.priority || approval.priority;
            if (this.currentFilters.priority !== 'all') {
                if (this.currentFilters.priority === 'high' && priority !== 1) return false;
                if (this.currentFilters.priority === 'medium' && priority !== 2) return false;
                if (this.currentFilters.priority === 'low' && priority !== 3) return false;
            }
            
            if (this.currentFilters.search) {
                const searchText = `${approval.booking_title} ${approval.venue_name} ${approval.requester_name}`.toLowerCase();
                if (!searchText.includes(this.currentFilters.search)) return false;
            }
            
            return true;
        });
    }

    sortApprovals(approvals) {
        const sortBy = document.getElementById('sortFilter')?.value || 'date_asc';
        
        return [...approvals].sort((a, b) => {
            switch (sortBy) {
                case 'date_asc':
                    return new Date(a.request_date) - new Date(b.request_date);
                case 'date_desc':
                    return new Date(b.request_date) - new Date(a.request_date);
                case 'priority_high':
                    return (a.booking?.priority || a.priority) - (b.booking?.priority || b.priority);
                case 'priority_low':
                    return (b.booking?.priority || b.priority) - (a.booking?.priority || a.priority);
                default:
                    return 0;
            }
        });
    }

    renderApprovalCard(approval) {
        const priority = approval.booking?.priority || approval.priority;
        const priorityClass = priority === 1 ? 'high' : priority === 2 ? 'medium' : 'low';
        const priorityIcon = priority === 1 ? 'fa-fire' : priority === 2 ? 'fa-chart-line' : 'fa-leaf';
        const priorityName = priority === 1 ? 'High Priority' : priority === 2 ? 'Medium Priority' : 'Low Priority';
        
        const stageIcon = this.getStageIcon(approval.stage);
        const stageName = this.getStageName(approval.stage);
        
        return `
            <div class="approval-card" data-approval-id="${approval.id}" data-stage="${approval.stage}" data-priority="${priority}">
                <div class="card-header">
                    <div class="stage-badge stage-${approval.stage}">
                        <i class="fas ${stageIcon}"></i>
                        ${stageName} Approval
                    </div>
                    <div class="priority-badge priority-${priorityClass}">
                        <i class="fas ${priorityIcon}"></i>
                        ${priorityName}
                    </div>
                </div>
                <div class="card-body">
                    <div class="event-title">
                        <input type="checkbox" class="approval-select" data-id="${approval.id}" onchange="window.approvalWorkflow.updateSelection()">
                        <i class="fas fa-calendar-alt"></i>
                        ${this.escapeHtml(approval.booking_title)}
                    </div>
                    <div class="event-details">
                        ${this.formatDateTime(approval.booking_start_time)} - ${this.formatDateTime(approval.booking_end_time, 'time')}
                    </div>
                    <div class="detail-row">
                        <i class="fas fa-map-marker-alt"></i>
                        <span>${this.escapeHtml(approval.venue_name)}</span>
                    </div>
                    <div class="detail-row">
                        <i class="fas fa-users"></i>
                        <span>Expected: ${approval.expected_attendees || 'Not specified'} attendees</span>
                    </div>
                    <div class="requester-info">
                        <div class="detail-row">
                            <i class="fas fa-user"></i>
                            <span><strong>Requested by:</strong> ${this.escapeHtml(approval.requester_name || 'N/A')}</span>
                        </div>
                        <div class="detail-row">
                            <i class="fas fa-clock"></i>
                            <span>Requested on: ${this.formatDateTime(approval.request_date)}</span>
                        </div>
                    </div>
                    ${approval.special_requests ? `
                    <div class="detail-row special-request">
                        <i class="fas fa-clipboard-list"></i>
                        <span><strong>Special Request:</strong> ${this.escapeHtml(approval.special_requests.substring(0, 100))}${approval.special_requests.length > 100 ? '...' : ''}</span>
                    </div>
                    ` : ''}
                </div>
                <div class="card-footer">
                    <button class="btn-approve" onclick="window.approvalWorkflow.openApproveModal(${approval.id}, '${this.escapeHtml(approval.booking_title)}')">
                        <i class="fas fa-check-circle"></i> Approve
                    </button>
                    <button class="btn-reject" onclick="window.approvalWorkflow.openRejectModal(${approval.id}, '${this.escapeHtml(approval.booking_title)}')">
                        <i class="fas fa-times-circle"></i> Reject
                    </button>
                    <button class="btn-view" onclick="window.approvalWorkflow.viewDetails(${approval.id})">
                        <i class="fas fa-eye"></i> Details
                    </button>
                </div>
            </div>
        `;
    }

    attachCardEventListeners() {
        // Additional event listeners for dynamic elements can be added here
    }

    updateSelection() {
        const checkboxes = document.querySelectorAll('.approval-select:checked');
        const selectedCount = document.getElementById('selectedCount');
        const batchActions = document.getElementById('batchActions');
        
        if (selectedCount) {
            selectedCount.textContent = `${checkboxes.length} selected`;
        }
        
        if (batchActions) {
            batchActions.classList.toggle('hidden', checkboxes.length === 0);
        }
        
        const selectAll = document.getElementById('selectAllCheckbox');
        const allCheckboxes = document.querySelectorAll('.approval-select');
        if (selectAll && allCheckboxes.length > 0) {
            selectAll.checked = checkboxes.length === allCheckboxes.length;
        }
    }

    toggleSelectAll() {
        const selectAll = document.getElementById('selectAllCheckbox');
        const checkboxes = document.querySelectorAll('.approval-select');
        checkboxes.forEach(cb => cb.checked = selectAll.checked);
        this.updateSelection();
    }

    async batchApprove() {
        const selectedIds = this.getSelectedApprovalIds();
        if (selectedIds.length === 0) return;
        
        if (confirm(`Approve ${selectedIds.length} pending approval(s)?`)) {
            await this.processBatchApprovals(selectedIds, 'approve');
        }
    }

    async batchReject() {
        const selectedIds = this.getSelectedApprovalIds();
        if (selectedIds.length === 0) return;
        
        const reason = prompt('Please provide a reason for rejection:');
        if (reason === null) return;
        
        await this.processBatchApprovals(selectedIds, 'reject', reason);
    }

    getSelectedApprovalIds() {
        const checkboxes = document.querySelectorAll('.approval-select:checked');
        return Array.from(checkboxes).map(cb => parseInt(cb.dataset.id));
    }

    async processBatchApprovals(approvalIds, action, comments = '') {
        try {
            const response = await fetch(`${this.apiEndpoint}/batch`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify({ approval_ids: approvalIds, action, comments })
            });
            
            const data = await response.json();
            if (data.success) {
                this.showNotification(`Processed ${data.processed} approvals`, 'success');
                this.loadPendingApprovals();
            } else {
                throw new Error(data.error || 'Batch processing failed');
            }
        } catch (error) {
            console.error('Batch approval error:', error);
            this.showNotification(error.message, 'error');
        }
    }

    async approveBooking(approvalId = null) {
        const id = approvalId || this.currentApproval?.id;
        if (!id) return;
        
        const comments = this.elements.commentsInput ? this.elements.commentsInput.value : '';
        
        this.showLoading(true);
        
        try {
            const response = await fetch(`${this.apiEndpoint}/${id}/approve`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify({ comments })
            });
            
            const data = await response.json();
            
            if (response.ok) {
                this.showNotification('Booking approved successfully!', 'success');
                this.removeApproval(id);
                this.updateStats();
                this.emit('approved', { id, comments });
                
                if (this.elements.commentsInput) {
                    this.elements.commentsInput.value = '';
                }
            } else {
                throw new Error(data.error || 'Approval failed');
            }
        } catch (error) {
            console.error('Approval error:', error);
            this.showNotification(error.message, 'error');
        } finally {
            this.showLoading(false);
            this.closeModal();
        }
    }

    async rejectBooking(approvalId = null) {
        const id = approvalId || this.currentApproval?.id;
        if (!id) return;
        
        const comments = this.elements.commentsInput ? this.elements.commentsInput.value : '';
        
        if (!comments) {
            this.showNotification('Please provide a reason for rejection', 'warning');
            return;
        }
        
        this.showLoading(true);
        
        try {
            const response = await fetch(`${this.apiEndpoint}/${id}/reject`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify({ comments })
            });
            
            const data = await response.json();
            
            if (response.ok) {
                this.showNotification('Booking rejected', 'info');
                this.removeApproval(id);
                this.updateStats();
                this.emit('rejected', { id, comments });
                
                if (this.elements.commentsInput) {
                    this.elements.commentsInput.value = '';
                }
            } else {
                throw new Error(data.error || 'Rejection failed');
            }
        } catch (error) {
            console.error('Rejection error:', error);
            this.showNotification(error.message, 'error');
        } finally {
            this.showLoading(false);
            this.closeModal();
        }
    }

    removeApproval(approvalId) {
        this.pendingApprovals = this.pendingApprovals.filter(a => a.id !== approvalId);
        this.renderApprovals();
        this.updateNotificationBadge();
    }

    async viewDetails(approvalId) {
        try {
            const response = await fetch(`${this.apiEndpoint}/${approvalId}`);
            const approval = await response.json();
            this.currentApproval = approval;
            this.showDetailsModal(approval);
        } catch (error) {
            console.error('Error loading details:', error);
            this.showNotification('Failed to load approval details', 'error');
        }
    }

    showDetailsModal(approval) {
        const modalHtml = `
            <div id="approvalModal" class="modal active">
                <div class="modal-content">
                    <div class="modal-header">
                        <h3 class="modal-title">
                            <i class="fas fa-clipboard-list"></i>
                            Approval Details
                        </h3>
                        <button class="modal-close" onclick="window.approvalWorkflow.closeModal()">&times;</button>
                    </div>
                    <div class="modal-body">
                        <div class="approval-details">
                            <div class="detail-section">
                                <h4>Booking Information</h4>
                                <div class="detail-row"><span class="label">Title:</span><span class="value">${this.escapeHtml(approval.booking_title)}</span></div>
                                <div class="detail-row"><span class="label">Venue:</span><span class="value">${this.escapeHtml(approval.venue_name)}</span></div>
                                <div class="detail-row"><span class="label">Date & Time:</span><span class="value">${this.formatDateTime(approval.booking_start_time)} - ${this.formatDateTime(approval.booking_end_time, 'time')}</span></div>
                                <div class="detail-row"><span class="label">Requester:</span><span class="value">${this.escapeHtml(approval.requester_name)} (${this.escapeHtml(approval.requester_email)})</span></div>
                            </div>
                            <div class="detail-section">
                                <h4>Approval Timeline</h4>
                                <div class="approval-timeline">
                                    ${this.renderTimeline(approval.timeline)}
                                </div>
                            </div>
                            <div class="detail-section">
                                <label>Comments</label>
                                <textarea id="approvalComments" rows="3" placeholder="Add your comments..."></textarea>
                            </div>
                        </div>
                    </div>
                    <div class="modal-actions">
                        <button class="btn-approve" onclick="window.approvalWorkflow.approveBooking()">
                            <i class="fas fa-check-circle"></i> Approve
                        </button>
                        <button class="btn-reject" onclick="window.approvalWorkflow.rejectBooking()">
                            <i class="fas fa-times-circle"></i> Reject
                        </button>
                        <button class="btn-secondary" onclick="window.approvalWorkflow.closeModal()">Cancel</button>
                    </div>
                </div>
            </div>
        `;
        
        const existingModal = document.getElementById('approvalModal');
        if (existingModal) existingModal.remove();
        
        document.body.insertAdjacentHTML('beforeend', modalHtml);
        this.elements.commentsInput = document.getElementById('approvalComments');
    }

    renderTimeline(timeline) {
        if (!timeline || timeline.length === 0) {
            return '<p>No timeline data available</p>';
        }
        
        return timeline.map(step => `
            <div class="timeline-step ${step.status}">
                <div class="step-icon"><i class="fas ${step.icon}"></i></div>
                <div class="step-content">
                    <div class="step-title">${step.title}</div>
                    <div class="step-time">${step.time || 'Pending'}</div>
                    <div class="step-comment">${step.comment || ''}</div>
                </div>
            </div>
        `).join('');
    }

    async updateStats() {
        if (!this.elements.approvalStats) return;
        
        try {
            const response = await fetch(`${this.apiEndpoint}/stats`);
            const stats = await response.json();
            
            this.elements.approvalStats.innerHTML = `
                <div class="stats-grid">
                    <div class="stat-card"><div class="stat-value">${stats.total_pending}</div><div class="stat-label">Pending</div></div>
                    <div class="stat-card"><div class="stat-value">${stats.approved_today || 0}</div><div class="stat-label">Approved Today</div></div>
                    <div class="stat-card"><div class="stat-value">${stats.rejected_today || 0}</div><div class="stat-label">Rejected Today</div></div>
                    <div class="stat-card"><div class="stat-value">${stats.avg_response_time || 0}</div><div class="stat-label">Avg Response (min)</div></div>
                </div>
            `;
        } catch (error) {
            console.error('Error loading stats:', error);
        }
    }

    updateNotificationBadge() {
        if (!this.elements.notificationBadge) return;
        
        const count = this.pendingApprovals.length;
        if (count > 0) {
            this.elements.notificationBadge.textContent = count > 99 ? '99+' : count;
            this.elements.notificationBadge.style.display = 'flex';
        } else {
            this.elements.notificationBadge.style.display = 'none';
        }
    }

    startAutoRefresh() {
        if (!this.autoRefresh) return;
        this.stopAutoRefresh();
        this.pollTimer = setInterval(() => this.loadPendingApprovals(), this.pollInterval);
    }

    stopAutoRefresh() {
        if (this.pollTimer) {
            clearInterval(this.pollTimer);
            this.pollTimer = null;
        }
    }

    closeModal() {
        const modal = document.getElementById('approvalModal');
        if (modal) modal.remove();
        this.currentApproval = null;
    }

    openApproveModal(approvalId, title) {
        this.currentApproval = { id: approvalId };
        const modalHtml = `
            <div id="quickApproveModal" class="modal active">
                <div class="modal-content" style="max-width: 400px;">
                    <div class="modal-header">
                        <h3 class="modal-title"><i class="fas fa-check-circle" style="color: #00ff88;"></i> Approve Booking</h3>
                        <button class="modal-close" onclick="document.getElementById('quickApproveModal')?.remove()">&times;</button>
                    </div>
                    <div class="modal-body">
                        <p>Approve "${this.escapeHtml(title)}"?</p>
                        <div class="form-group"><label>Comments (Optional)</label><textarea id="quickApproveComments" rows="2"></textarea></div>
                    </div>
                    <div class="modal-actions">
                        <button class="btn-approve" onclick="window.approvalWorkflow.approveBooking(${approvalId})">Confirm</button>
                        <button class="btn-secondary" onclick="document.getElementById('quickApproveModal')?.remove()">Cancel</button>
                    </div>
                </div>
            </div>
        `;
        document.body.insertAdjacentHTML('beforeend', modalHtml);
        this.elements.commentsInput = document.getElementById('quickApproveComments');
    }

    openRejectModal(approvalId, title) {
        this.currentApproval = { id: approvalId };
        const modalHtml = `
            <div id="quickRejectModal" class="modal active">
                <div class="modal-content" style="max-width: 400px;">
                    <div class="modal-header">
                        <h3 class="modal-title"><i class="fas fa-times-circle" style="color: #ff3366;"></i> Reject Booking</h3>
                        <button class="modal-close" onclick="document.getElementById('quickRejectModal')?.remove()">&times;</button>
                    </div>
                    <div class="modal-body">
                        <p>Reject "${this.escapeHtml(title)}"?</p>
                        <div class="form-group"><label>Reason *</label><textarea id="quickRejectReason" rows="2" required></textarea></div>
                    </div>
                    <div class="modal-actions">
                        <button class="btn-reject" onclick="window.approvalWorkflow.rejectBooking(${approvalId})">Confirm</button>
                        <button class="btn-secondary" onclick="document.getElementById('quickRejectModal')?.remove()">Cancel</button>
                    </div>
                </div>
            </div>
        `;
        document.body.insertAdjacentHTML('beforeend', modalHtml);
        this.elements.commentsInput = document.getElementById('quickRejectReason');
    }

    getStageIcon(stage) {
        const icons = { faculty: 'fa-chalkboard-user', admin: 'fa-user-tie', security: 'fa-shield-alt' };
        return icons[stage] || 'fa-user';
    }

    getStageName(stage) {
        const names = { faculty: 'Faculty', admin: 'Admin', security: 'Security' };
        return names[stage] || stage;
    }

    formatDateTime(dateStr, format = 'full') {
        if (!dateStr) return 'N/A';
        const date = new Date(dateStr);
        if (format === 'time') return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        return date.toLocaleString();
    }

    playNotificationSound() {
        try {
            const audio = new Audio('/static/sounds/notification.mp3');
            audio.volume = 0.3;
            audio.play().catch(e => console.log('Audio play failed:', e));
        } catch (e) { console.log('Audio not supported'); }
    }

    showLoading(show) {
        const loader = document.getElementById('globalLoader');
        if (loader) loader.style.display = show ? 'flex' : 'none';
    }

    showNotification(message, type) {
        const flashContainer = document.querySelector('.flash-container');
        if (!flashContainer) return;
        const toast = document.createElement('div');
        toast.className = `flash-message flash-${type}`;
        toast.innerHTML = `<div class="flash-icon"><i class="fas fa-${type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-circle' : 'info-circle'}"></i></div><div class="flash-content"><span>${this.escapeHtml(message)}</span></div><button class="flash-close">&times;</button><div class="flash-progress"></div>`;
        flashContainer.appendChild(toast);
        setTimeout(() => { toast.style.animation = 'slideOut 0.5s ease forwards'; setTimeout(() => toast.remove(), 500); }, 5000);
        toast.querySelector('.flash-close').addEventListener('click', () => { toast.style.animation = 'slideOut 0.3s ease forwards'; setTimeout(() => toast.remove(), 300); });
    }

    showError(message) { this.showNotification(message, 'error'); }
    escapeHtml(str) { if (!str) return ''; return str.replace(/[&<>]/g, m => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[m])); }
    on(event, callback) { if (!this.listeners.has(event)) this.listeners.set(event, []); this.listeners.get(event).push(callback); }
    emit(event, data) { if (this.listeners.has(event)) this.listeners.get(event).forEach(cb => cb(data)); }
    destroy() { this.stopAutoRefresh(); if (this.wsConnection) this.wsConnection.close(); this.listeners.clear(); }
}

// Initialize
let approvalWorkflow = null;
document.addEventListener('DOMContentLoaded', () => { approvalWorkflow = new ApprovalWorkflowManager(); });
window.approvalWorkflow = approvalWorkflow;