"""
Approval Service - Multi-level Approval Workflow Management
Handles faculty → admin → security approval chain with priority handling
"""

from datetime import datetime, timedelta
from flask import current_app
from app import db
from app.models import VenueBooking, BookingStatus
from app.models import VenueApprovalRequest, VenueApprovalRule
from app.models import User

class ApprovalService:
    """
    Service class for managing multi-level approval workflows
    Handles faculty → admin → security approval chain
    """
    
    # Approval stages in order
    APPROVAL_STAGES = ['faculty', 'admin', 'security']
    
    # Stage display names
    STAGE_NAMES = {
        'faculty': 'Faculty Approval',
        'admin': 'Admin Approval',
        'security': 'Security Clearance'
    }
    
    # Stage icons for UI
    STAGE_ICONS = {
        'faculty': 'fa-chalkboard-user',
        'admin': 'fa-user-tie',
        'security': 'fa-shield-alt'
    }
    
    @classmethod
    def initiate_approval(cls, booking_id):
        """
        Start approval workflow for a booking
        
        Args:
            booking_id: ID of the booking to approve
            
        Returns:
            bool: True if initiated successfully
        """
        try:
            booking = VenueBooking.query.get(booking_id)
            if not booking:
                raise ValueError(f"Booking {booking_id} not found")
            
            # Get approval rules based on booking details
            rules = cls._get_approval_rules(booking)
            
            # Create approval requests for each required stage
            for stage in cls.APPROVAL_STAGES:
                if cls._requires_approval(stage, booking, rules):
                    # Find appropriate approver for this stage
                    approver = cls._get_approver_for_stage(stage, booking)
                    
                    if not approver:
                        current_app.logger.warning(f"No approver found for {stage} stage for booking {booking_id}")
                        continue
                    
                    # Check if approval request already exists
                    existing = VenueApprovalRequest.query.filter_by(
                        booking_id=booking_id,
                        stage=stage,
                        status='pending'
                    ).first()
                    
                    if existing:
                        continue
                    
                    # Create approval request
                    approval = VenueApprovalRequest(
                        booking_id=booking_id,
                        stage=stage,
                        approver_id=approver.id,
                        status='pending',
                        request_date=datetime.utcnow()
                    )
                    
                    db.session.add(approval)
                    
                    # Send notification to approver
                    from app.tasks.venue_tasks import send_approval_notification_task as send_approval_notification
                    send_approval_notification.delay(approval.id)
            
            # Update booking status based on first required stage
            first_stage = cls._get_first_required_stage(booking, rules)
            if first_stage == 'faculty':
                booking.status = BookingStatus.PENDING_FACULTY
            elif first_stage == 'admin':
                booking.status = BookingStatus.PENDING_ADMIN
            elif first_stage == 'security':
                booking.status = BookingStatus.PENDING_SECURITY
            
            db.session.commit()
            current_app.logger.info(f"Approval workflow initiated for booking {booking_id}")
            return True
            
        except Exception as e:
            current_app.logger.error(f"Failed to initiate approval for booking {booking_id}: {e}")
            db.session.rollback()
            return False
    
    @classmethod
    def process_approval(cls, approval_id, user_id, approved, comments=None):
        """
        Process an approval request
        
        Args:
            approval_id: ID of the approval request
            user_id: ID of the user processing the approval
            approved: Boolean indicating approval or rejection
            comments: Optional comments from approver
            
        Returns:
            dict: Result with status and next steps
        """
        try:
            approval = VenueApprovalRequest.query.get(approval_id)
            if not approval:
                raise ValueError(f"Approval {approval_id} not found")
            
            booking = approval.booking
            
            # Verify user is the approver
            if approval.approver_id != user_id:
                raise PermissionError("User is not authorized to process this approval")
            
            # Check if already processed
            if approval.status != 'pending':
                raise ValueError(f"Approval already {approval.status}")
            
            # Update approval record
            approval.status = 'approved' if approved else 'rejected'
            approval.response_date = datetime.utcnow()
            approval.comments = comments
            
            # Log history
            from app.models import VenueBookingHistory
            history = VenueBookingHistory(
                booking_id=booking.id,
                action='approved' if approved else 'rejected',
                old_status=booking.status.value,
                new_status=booking.status.value,
                comment=comments,
                performed_by=user_id
            )
            db.session.add(history)
            
            if approved:
                # Mark this stage as approved in booking
                if approval.stage == 'faculty':
                    booking.faculty_approved = True
                    booking.faculty_approved_at = datetime.utcnow()
                    booking.faculty_approved_by = user_id
                    booking.status = BookingStatus.PENDING_ADMIN
                    
                elif approval.stage == 'admin':
                    booking.admin_approved = True
                    booking.admin_approved_at = datetime.utcnow()
                    booking.admin_approved_by = user_id
                    booking.status = BookingStatus.PENDING_SECURITY
                    
                elif approval.stage == 'security':
                    booking.security_approved = True
                    booking.security_approved_at = datetime.utcnow()
                    booking.security_approved_by = user_id
                    booking.status = BookingStatus.APPROVED
                
                # Check if fully approved
                if cls.is_fully_approved(booking):
                    booking.status = BookingStatus.CONFIRMED
                    current_app.logger.info(f"Booking {booking.id} fully approved and confirmed")
                    
                    # Send confirmation to requester
                    from app.services.notification_service import NotificationService
                    NotificationService.send_booking_confirmation(booking.id)
                    
                    result = {
                        'status': 'completed',
                        'message': 'Booking fully approved and confirmed',
                        'next_stage': None
                    }
                else:
                    # Get next pending approval
                    next_approval = cls.get_next_pending_approval(booking.id)
                    result = {
                        'status': 'stage_completed',
                        'message': f'{cls.STAGE_NAMES[approval.stage]} completed',
                        'next_stage': next_approval.stage if next_approval else None,
                        'next_stage_name': cls.STAGE_NAMES.get(next_approval.stage) if next_approval else None
                    }
            else:
                # Rejected - cancel the entire booking
                booking.status = BookingStatus.REJECTED
                booking.rejection_reason = comments
                booking.rejection_stage = approval.stage
                
                # Cancel all pending approvals for this booking
                pending_approvals = VenueApprovalRequest.query.filter_by(
                    booking_id=booking.id,
                    status='pending'
                ).all()
                
                for pending in pending_approvals:
                    pending.status = 'cancelled'
                    pending.comments = f"Cancelled due to rejection at {approval.stage} stage"
                
                result = {
                    'status': 'rejected',
                    'message': f'Booking rejected at {cls.STAGE_NAMES[approval.stage]} stage',
                    'rejection_stage': approval.stage,
                    'rejection_reason': comments
                }
            
            db.session.commit()
            current_app.logger.info(f"Approval {approval_id} processed: {approved}")
            
            return result
            
        except Exception as e:
            current_app.logger.error(f"Failed to process approval {approval_id}: {e}")
            db.session.rollback()
            raise
    
    @classmethod
    def get_pending_approvals_for_user(cls, user_id):
        """
        Get all pending approvals for a specific user
        
        Args:
            user_id: ID of the user
            
        Returns:
            list: List of pending approval requests
        """
        user = User.query.get(user_id)
        if not user:
            return []
        
        # Determine which stage this user handles based on role
        if user.role == 'faculty':
            stage = 'faculty'
        elif user.role == 'admin':
            stage = 'admin'
        elif user.role == 'security':
            stage = 'security'
        else:
            return []
        
        pending = VenueApprovalRequest.query.filter(
            VenueApprovalRequest.stage == stage,
            VenueApprovalRequest.status == 'pending',
            VenueApprovalRequest.approver_id == user_id
        ).order_by(VenueApprovalRequest.request_date).all()
        
        return pending
    
    @classmethod
    def get_booking_approval_status(cls, booking_id):
        """
        Get complete approval status for a booking
        
        Args:
            booking_id: ID of the booking
            
        Returns:
            dict: Approval status with timeline
        """
        booking = VenueBooking.query.get(booking_id)
        if not booking:
            return None
        
        approvals = VenueApprovalRequest.query.filter_by(booking_id=booking_id).all()
        
        status = {
            'booking_id': booking_id,
            'booking_title': booking.title,
            'current_status': booking.status.value,
            'is_fully_approved': cls.is_fully_approved(booking),
            'stages': []
        }
        
        for stage in cls.APPROVAL_STAGES:
            stage_approval = next((a for a in approvals if a.stage == stage), None)
            
            stage_info = {
                'stage': stage,
                'name': cls.STAGE_NAMES[stage],
                'icon': cls.STAGE_ICONS[stage],
                'required': cls._is_stage_required(booking, stage),
                'status': None,
                'approver': None,
                'approved_at': None,
                'comments': None
            }
            
            if stage_approval:
                stage_info['status'] = stage_approval.status
                if stage_approval.approver:
                    stage_info['approver'] = {
                        'id': stage_approval.approver.id,
                        'name': stage_approval.approver.username,
                        'email': stage_approval.approver.email,
                        'role': stage_approval.approver.role
                    }
                stage_info['approved_at'] = stage_approval.response_date
                stage_info['comments'] = stage_approval.comments
            elif cls._is_stage_required(booking, stage):
                stage_info['status'] = 'pending'
            else:
                stage_info['status'] = 'not_required'
            
            status['stages'].append(stage_info)
        
        return status
    
    @classmethod
    def get_next_pending_approval(cls, booking_id):
        """
        Get the next pending approval for a booking
        
        Args:
            booking_id: ID of the booking
            
        Returns:
            VenueApprovalRequest or None: Next pending approval
        """
        booking = VenueBooking.query.get(booking_id)
        if not booking:
            return None
        
        # Get all pending approvals in order
        pending = VenueApprovalRequest.query.filter(
            VenueApprovalRequest.booking_id == booking_id,
            VenueApprovalRequest.status == 'pending'
        ).order_by(VenueApprovalRequest.request_date).all()
        
        if pending:
            return pending[0]
        
        return None
    
    @classmethod
    def is_fully_approved(cls, booking):
        """
        Check if a booking has received all required approvals
        
        Args:
            booking: VenueBooking object
            
        Returns:
            bool: True if all required approvals are complete
        """
        # Get rules for this booking
        rules = cls._get_approval_rules(booking)
        
        # Check each required stage
        if rules.requires_faculty and not booking.faculty_approved:
            return False
        if rules.requires_admin and not booking.admin_approved:
            return False
        if rules.requires_security and not booking.security_approved:
            return False
        
        return True
    
    @classmethod
    def auto_approve_eligible_bookings(cls):
        """
        Automatically approve bookings that meet auto-approval criteria
        
        Returns:
            int: Number of bookings auto-approved
        """
        auto_approved = 0
        
        try:
            # Get all pending faculty approvals
            pending = VenueApprovalRequest.query.filter(
                VenueApprovalRequest.stage == 'faculty',
                VenueApprovalRequest.status == 'pending'
            ).all()
            
            for approval in pending:
                booking = approval.booking
                rules = cls._get_approval_rules(booking)
                
                # Check if auto-approval threshold is met
                if rules.auto_approve_if and booking.expected_attendees:
                    # Parse auto-approve condition (e.g., "attendees < 50")
                    condition = rules.auto_approve_if
                    if 'attendees <' in condition:
                        threshold = int(condition.split('<')[1].strip())
                        if booking.expected_attendees < threshold:
                            # Auto-approve
                            result = cls.process_approval(
                                approval.id,
                                approval.approver_id,
                                True,
                                comments="Auto-approved based on rules"
                            )
                            if result['status'] in ['stage_completed', 'completed']:
                                auto_approved += 1
                                current_app.logger.info(f"Auto-approved booking {booking.id}")
            
            db.session.commit()
            
        except Exception as e:
            current_app.logger.error(f"Auto-approval process failed: {e}")
        
        return auto_approved
    
    @classmethod
    def timeout_expired_approvals(cls, timeout_hours=48):
        """
        Automatically reject approvals that have timed out
        
        Args:
            timeout_hours: Number of hours before timeout
            
        Returns:
            int: Number of approvals timed out
        """
        timed_out = 0
        cutoff_time = datetime.utcnow() - timedelta(hours=timeout_hours)
        
        try:
            expired = VenueApprovalRequest.query.filter(
                VenueApprovalRequest.status == 'pending',
                VenueApprovalRequest.request_date < cutoff_time
            ).all()
            
            for approval in expired:
                result = cls.process_approval(
                    approval.id,
                    approval.approver_id,
                    False,
                    comments=f"Auto-rejected: No response within {timeout_hours} hours"
                )
                timed_out += 1
                current_app.logger.info(f"Timed out approval {approval.id} for booking {approval.booking_id}")
            
            db.session.commit()
            
        except Exception as e:
            current_app.logger.error(f"Timeout processing failed: {e}")
        
        return timed_out
    
    @classmethod
    def get_approval_statistics(cls):
        """
        Get approval statistics
        
        Returns:
            dict: Statistics about approvals
        """
        stats = {
            'total_pending': VenueApprovalRequest.query.filter_by(status='pending').count(),
            'total_approved': VenueApprovalRequest.query.filter_by(status='approved').count(),
            'total_rejected': VenueApprovalRequest.query.filter_by(status='rejected').count(),
            'total_cancelled': VenueApprovalRequest.query.filter_by(status='cancelled').count(),
            'by_stage': {},
            'avg_response_time': None
        }
        
        # Statistics by stage
        for stage in cls.APPROVAL_STAGES:
            stats['by_stage'][stage] = {
                'pending': VenueApprovalRequest.query.filter_by(stage=stage, status='pending').count(),
                'approved': VenueApprovalRequest.query.filter_by(stage=stage, status='approved').count(),
                'rejected': VenueApprovalRequest.query.filter_by(stage=stage, status='rejected').count()
            }
        
        # Calculate average response time for completed approvals
        from sqlalchemy import func
        avg_time = db.session.query(
            func.avg(func.extract('epoch', VenueApprovalRequest.response_date - VenueApprovalRequest.request_date))
        ).filter(
            VenueApprovalRequest.status.in_(['approved', 'rejected']),
            VenueApprovalRequest.response_date.isnot(None)
        ).scalar()
        
        if avg_time:
            stats['avg_response_time'] = round(avg_time / 3600, 1)  # Convert to hours
        
        return stats
    
    # ============================================
    # Private Helper Methods
    # ============================================
    
    @classmethod
    def _get_approval_rules(cls, booking):
        """
        Get approval rules for a booking
        
        Args:
            booking: VenueBooking object
            
        Returns:
            VenueApprovalRule: Rules for this booking
        """
        # Try to find specific rule for this venue type and event type
        rule = VenueApprovalRule.query.filter_by(
            venue_type=booking.venue.type.value,
            event_type=booking.event_type
        ).first()
        
        if not rule:
            # Try generic rule for event type
            rule = VenueApprovalRule.query.filter_by(
                venue_type='all',
                event_type=booking.event_type
            ).first()
        
        if not rule:
            # Create default rule
            rule = VenueApprovalRule(
                venue_type='all',
                event_type=booking.event_type,
                requires_faculty=True,
                requires_admin=True,
                requires_security=True,
                auto_approve_if=None
            )
        
        return rule
    
    @classmethod
    def _requires_approval(cls, stage, booking, rules):
        """
        Check if a specific stage requires approval
        
        Args:
            stage: Approval stage name
            booking: VenueBooking object
            rules: VenueApprovalRule object
            
        Returns:
            bool: True if approval is required
        """
        if stage == 'faculty':
            return rules.requires_faculty
        elif stage == 'admin':
            return rules.requires_admin
        elif stage == 'security':
            return rules.requires_security
        return False
    
    @classmethod
    def _is_stage_required(cls, booking, stage):
        """
        Check if a stage is required for a booking
        
        Args:
            booking: VenueBooking object
            stage: Stage name
            
        Returns:
            bool: True if stage is required
        """
        rules = cls._get_approval_rules(booking)
        
        if stage == 'faculty':
            return rules.requires_faculty
        elif stage == 'admin':
            return rules.requires_admin
        elif stage == 'security':
            return rules.requires_security
        
        return False
    
    @classmethod
    def _get_first_required_stage(cls, booking, rules):
        """
        Get the first required approval stage
        
        Args:
            booking: VenueBooking object
            rules: VenueApprovalRule object
            
        Returns:
            str: First required stage or None
        """
        for stage in cls.APPROVAL_STAGES:
            if cls._requires_approval(stage, booking, rules):
                return stage
        return None
    
    @classmethod
    def _get_approver_for_stage(cls, stage, booking):
        """
        Get the approver for a specific stage
        
        Args:
            stage: Approval stage name
            booking: VenueBooking object
            
        Returns:
            User: Approver user or None
        """
        # This can be customized based on organizational structure
        if stage == 'faculty':
            approver = User.query.filter_by(role='faculty').first()
        elif stage == 'admin':
            approver = User.query.filter_by(role='admin').first()
        elif stage == 'security':
            approver = User.query.filter_by(role='security').first()
        else:
            approver = None
        
        return approver