"""
Approval Routes - Multi-level Approval Workflow
Handles faculty → admin → security approval chain
"""

from datetime import datetime
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, current_app
from flask_login import login_required, current_user
from sqlalchemy import func, and_, or_

from app import db
from app.models import VenueBooking, BookingStatus, VenueBookingHistory, VenueApprovalRequest, VenueApprovalRule, User
from app.services.approval_service import ApprovalService
from app.services.notification_service import NotificationService

# Create blueprint
approval_bp = Blueprint('approval', __name__, url_prefix='/approvals')


# ============================================
# Approval Views
# ============================================

@approval_bp.route('/')
@login_required
def index():
    """Approval dashboard - shows pending approvals based on user role"""
    if current_user.role not in ['faculty', 'admin', 'security']:
        flash('You do not have permission to access approvals', 'danger')
        return redirect(url_for('public.index'))
    
    # Get pending approvals for this user
    pending_approvals = ApprovalService.get_pending_approvals_for_user(current_user.id)
    
    # Get statistics
    stats = ApprovalService.get_approval_statistics()
    
    # Get recent approvals (last 30 days)
    recent_approvals = VenueApprovalRequest.query.filter(
        VenueApprovalRequest.status.in_(['approved', 'rejected']),
        VenueApprovalRequest.response_date >= datetime.utcnow().replace(day=1)
    ).order_by(VenueApprovalRequest.response_date.desc()).limit(20).all()
    
    return render_template('approval/index.html',
                          pending_approvals=pending_approvals,
                          stats=stats,
                          recent_approvals=recent_approvals,
                          user_role=current_user.role)


@approval_bp.route('/pending')
@login_required
def pending():
    """View all pending approvals for current user"""
    if current_user.role not in ['faculty', 'admin', 'security']:
        flash('You do not have permission to access approvals', 'danger')
        return redirect(url_for('public.index'))
    
    pending_approvals = ApprovalService.get_pending_approvals_for_user(current_user.id)
    
    return render_template('approval/pending.html', approvals=pending_approvals)


@approval_bp.route('/history')
@login_required
def history():
    """View approval history"""
    if current_user.role not in ['faculty', 'admin', 'security', 'admin']:
        flash('You do not have permission to access approval history', 'danger')
        return redirect(url_for('public.index'))
    
    # Get filter parameters
    status = request.args.get('status')
    stage = request.args.get('stage')
    
    query = VenueApprovalRequest.query
    
    if current_user.role != 'admin':
        query = query.filter_by(approver_id=current_user.id)
    
    if status:
        query = query.filter_by(status=status)
    if stage:
        query = query.filter_by(stage=stage)
    
    approvals = query.order_by(VenueApprovalRequest.response_date.desc()).paginate(
        page=request.args.get('page', 1, type=int),
        per_page=20
    )
    
    return render_template('approval/history.html', approvals=approvals)


@approval_bp.route('/<int:approval_id>')
@login_required
def detail(approval_id):
    """View approval details"""
    approval = VenueApprovalRequest.query.get_or_404(approval_id)
    booking = approval.booking
    
    # Check permissions
    if current_user.role not in ['admin'] and approval.approver_id != current_user.id and booking.created_by != current_user.id:
        flash('You do not have permission to view this approval', 'danger')
        return redirect(url_for('approval.index'))
    
    return render_template('approval/detail.html', approval=approval, booking=booking)


@approval_bp.route('/<int:approval_id>/process', methods=['GET', 'POST'])
@login_required
def process(approval_id):
    """Process an approval (approve or reject)"""
    approval = VenueApprovalRequest.query.get_or_404(approval_id)
    
    # Check if user is the approver
    if approval.approver_id != current_user.id:
        flash('You are not authorized to process this approval', 'danger')
        return redirect(url_for('approval.index'))
    
    # Check if already processed
    if approval.status != 'pending':
        flash(f'This approval has already been {approval.status}', 'warning')
        return redirect(url_for('approval.detail', approval_id=approval_id))
    
    if request.method == 'POST':
        action = request.form.get('action')
        comments = request.form.get('comments', '')
        
        if action not in ['approve', 'reject']:
            flash('Invalid action', 'danger')
            return redirect(url_for('approval.detail', approval_id=approval_id))
        
        try:
            # Process the approval
            result = ApprovalService.process_approval(
                approval_id=approval_id,
                user_id=current_user.id,
                approved=(action == 'approve'),
                comments=comments
            )
            
            # Send notification to requester
            NotificationService.send_approval_response_notification(approval_id, action == 'approve', comments)
            
            flash(result['message'], 'success' if result['status'] != 'rejected' else 'danger')
            
            # Redirect based on result
            if result['status'] == 'completed':
                return redirect(url_for('booking.view', booking_id=approval.booking_id))
            else:
                return redirect(url_for('approval.pending'))
                
        except Exception as e:
            flash(str(e), 'danger')
            return redirect(url_for('approval.detail', approval_id=approval_id))
    
    return render_template('approval/process.html', approval=approval)


@approval_bp.route('/batch', methods=['POST'])
@login_required
def batch_process():
    """Batch process multiple approvals"""
    if current_user.role not in ['faculty', 'admin', 'security']:
        return jsonify({'error': 'Unauthorized'}), 403
    
    approval_ids = request.form.getlist('approval_ids')
    action = request.form.get('action')
    comments = request.form.get('comments', '')
    
    if not approval_ids:
        flash('No approvals selected', 'warning')
        return redirect(url_for('approval.pending'))
    
    processed = 0
    failed = 0
    
    for approval_id in approval_ids:
        approval = VenueApprovalRequest.query.get(approval_id)
        if approval and approval.approver_id == current_user.id and approval.status == 'pending':
            try:
                result = ApprovalService.process_approval(
                    approval_id=int(approval_id),
                    user_id=current_user.id,
                    approved=(action == 'approve'),
                    comments=comments
                )
                processed += 1
            except Exception as e:
                failed += 1
    
    flash(f'Processed {processed} approvals. Failed: {failed}', 'success' if processed > 0 else 'warning')
    return redirect(url_for('approval.pending'))


# ============================================
# Approval Rules Management (Admin only)
# ============================================

@approval_bp.route('/rules')
@login_required
def rules():
    """Manage approval rules (admin only)"""
    if current_user.role != 'admin':
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('approval.index'))
    
    rules = VenueApprovalRule.query.all()
    return render_template('approval/rules.html', rules=rules)


@approval_bp.route('/rules/create', methods=['GET', 'POST'])
@login_required
def create_rule():
    """Create a new approval rule"""
    if current_user.role != 'admin':
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('approval.index'))
    
    if request.method == 'POST':
        try:
            rule = VenueApprovalRule(
                venue_type=request.form.get('venue_type'),
                event_type=request.form.get('event_type'),
                min_attendees=request.form.get('min_attendees', type=int) or None,
                requires_faculty=request.form.get('requires_faculty') == 'on',
                requires_admin=request.form.get('requires_admin') == 'on',
                requires_security=request.form.get('requires_security') == 'on',
                auto_approve_if=request.form.get('auto_approve_if') or None
            )
            db.session.add(rule)
            db.session.commit()
            flash('Approval rule created successfully', 'success')
            return redirect(url_for('approval.rules'))
        except Exception as e:
            flash(str(e), 'danger')
    
    return render_template('approval/rule_form.html')


@approval_bp.route('/rules/<int:rule_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_rule(rule_id):
    """Edit an approval rule"""
    if current_user.role != 'admin':
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('approval.index'))
    
    rule = VenueApprovalRule.query.get_or_404(rule_id)
    
    if request.method == 'POST':
        try:
            rule.venue_type = request.form.get('venue_type')
            rule.event_type = request.form.get('event_type')
            rule.min_attendees = request.form.get('min_attendees', type=int) or None
            rule.requires_faculty = request.form.get('requires_faculty') == 'on'
            rule.requires_admin = request.form.get('requires_admin') == 'on'
            rule.requires_security = request.form.get('requires_security') == 'on'
            rule.auto_approve_if = request.form.get('auto_approve_if') or None
            db.session.commit()
            flash('Approval rule updated successfully', 'success')
            return redirect(url_for('approval.rules'))
        except Exception as e:
            flash(str(e), 'danger')
    
    return render_template('approval/rule_form.html', rule=rule)


@approval_bp.route('/rules/<int:rule_id>/delete', methods=['POST'])
@login_required
def delete_rule(rule_id):
    """Delete an approval rule"""
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    rule = VenueApprovalRule.query.get_or_404(rule_id)
    db.session.delete(rule)
    db.session.commit()
    
    flash('Approval rule deleted successfully', 'success')
    return redirect(url_for('approval.rules'))


# ============================================
# API Endpoints
# ============================================

@approval_bp.route('/api/pending')
@login_required
def api_pending_approvals():
    """API endpoint to get pending approvals for current user"""
    if current_user.role not in ['faculty', 'admin', 'security']:
        return jsonify({'error': 'Unauthorized'}), 403
    
    pending = ApprovalService.get_pending_approvals_for_user(current_user.id)
    
    return jsonify([{
        'id': a.id,
        'booking_id': a.booking_id,
        'booking_title': a.booking.title,
        'stage': a.stage,
        'stage_name': ApprovalService.STAGE_NAMES.get(a.stage, a.stage),
        'requester_name': a.booking.created_by_username if hasattr(a.booking, 'created_by_username') else None,
        'venue_name': a.booking.venue.name,
        'start_time': a.booking.start_time.isoformat(),
        'end_time': a.booking.end_time.isoformat(),
        'request_date': a.request_date.isoformat(),
        'priority': a.booking.priority,
        'priority_name': a.booking.get_priority_level()
    } for a in pending])


@approval_bp.route('/api/booking/<int:booking_id>/status')
@login_required
def api_booking_approval_status(booking_id):
    """API endpoint to get approval status for a booking"""
    booking = VenueBooking.query.get_or_404(booking_id)
    
    # Check permissions
    if current_user.role not in ['admin', 'faculty', 'security'] and booking.created_by != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    status = ApprovalService.get_booking_approval_status(booking_id)
    return jsonify(status)


@approval_bp.route('/api/stats')
@login_required
def api_approval_stats():
    """API endpoint to get approval statistics"""
    if current_user.role not in ['admin', 'faculty', 'security']:
        return jsonify({'error': 'Unauthorized'}), 403
    
    stats = ApprovalService.get_approval_statistics()
    return jsonify(stats)


@approval_bp.route('/api/auto-approve', methods=['POST'])
@login_required
def api_auto_approve():
    """API endpoint to trigger auto-approval process (admin only)"""
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    count = ApprovalService.auto_approve_eligible_bookings()
    return jsonify({'message': f'Auto-approved {count} bookings', 'count': count})


@approval_bp.route('/api/timeout-expired', methods=['POST'])
@login_required
def api_timeout_expired():
    """API endpoint to process timed-out approvals (admin only)"""
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    timeout_hours = request.json.get('timeout_hours', 48)
    count = ApprovalService.timeout_expired_approvals(timeout_hours)
    return jsonify({'message': f'Timed out {count} approvals', 'count': count})


# ============================================
# Helper Functions
# ============================================

@approval_bp.context_processor
def utility_processor():
    """Add utility functions to template context"""
    return {
        'get_stage_name': lambda stage: ApprovalService.STAGE_NAMES.get(stage, stage),
        'get_stage_icon': lambda stage: ApprovalService.STAGE_ICONS.get(stage, 'fa-user'),
        'can_approve': lambda approval: approval.approver_id == current_user.id and approval.status == 'pending'
    }