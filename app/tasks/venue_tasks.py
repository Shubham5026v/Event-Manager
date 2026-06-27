"""
Venue Tasks - Celery Tasks for Automated Venue Management
Handles reminders, cleanup, notifications, and scheduled operations
"""

import logging
from datetime import datetime, timedelta
from flask import current_app, render_template
from celery import current_app as celery_app
from celery.utils.log import get_task_logger
from sqlalchemy import func, and_, or_

from app import db, mail
from app.models import VenueBooking, BookingStatus
from app.models import Venue, VenueMaintenanceSlot
from app.models import User
from app.models import VenueApprovalRequest
from app.services.notification_service import NotificationService
from app.services.priority_service import PriorityService

APPROVAL_STAGE_NAMES = {
    'faculty': 'Faculty Approval',
    'admin': 'Admin Approval',
    'security': 'Security Clearance'
}

# Initialize logger
logger = get_task_logger(__name__)


# ============================================
# Notification Tasks
# ============================================

@celery_app.task(bind=True, name='venue.send_booking_reminders')
def send_booking_reminders(self):
    """
    Send booking reminders to users
    - 24 hours before booking
    - 1 hour before booking
    - 15 minutes before booking
    """
    logger.info("Sending booking reminders...")
    
    try:
        now = datetime.utcnow()
        
        # Time thresholds
        reminders = [
            {'hours': 24, 'type': 'day_before'},
            {'hours': 1, 'type': 'hour_before'},
            {'minutes': 15, 'type': '15min_before'}
        ]
        
        sent_count = 0
        failed_count = 0
        
        for reminder in reminders:
            if 'hours' in reminder:
                threshold = now + timedelta(hours=reminder['hours'])
            else:
                threshold = now + timedelta(minutes=reminder['minutes'])
            
            # Find bookings that start around the threshold time
            time_range_start = threshold - timedelta(minutes=15)
            time_range_end = threshold + timedelta(minutes=15)
            
            bookings = VenueBooking.query.filter(
                VenueBooking.status.in_(['approved', 'confirmed']),
                VenueBooking.start_time >= time_range_start,
                VenueBooking.start_time <= time_range_end
            ).all()
            
            for booking in bookings:
                try:
                    # Send email reminder
                    NotificationService.send_booking_reminder(booking.id, reminder['type'])
                    sent_count += 1
                    logger.info(f"Sent {reminder['type']} reminder for booking {booking.id}")
                    
                except Exception as e:
                    logger.error(f"Failed to send reminder for booking {booking.id}: {e}")
                    failed_count += 1
        
        return {
            'status': 'completed',
            'sent': sent_count,
            'failed': failed_count,
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Booking reminders task failed: {e}")
        return {'status': 'failed', 'error': str(e)}


@celery_app.task(bind=True, name='venue.send_approval_notification')
def send_approval_notification_task(self, approval_id):
    """Send notification to approver about pending approval"""
    try:
        approval = VenueApprovalRequest.query.get(approval_id)
        if not approval:
            logger.error(f"Approval {approval_id} not found")
            return {'status': 'failed', 'error': 'Approval not found'}
        
        booking = approval.booking
        approver = User.query.get(approval.approver_id)
        
        if not approver or not approver.email:
            logger.error(f"Approver not found or no email for approval {approval_id}")
            return {'status': 'failed', 'error': 'No approver email'}
        
        context = {
            'approval': approval,
            'booking': booking,
            'venue': booking.venue,
            'stage': approval.stage,
            'stage_name': APPROVAL_STAGE_NAMES.get(approval.stage, approval.stage),
            'approval_url': f"/approvals/{approval.id}"
        }
        
        html_body = render_template('emails/approval_notification.html', **context)
        text_body = render_template('emails/approval_notification.txt', **context)
        
        from flask_mail import Message
        msg = Message(
            subject=f'Action Required: {booking.title} - {ApprovalService.STAGE_NAMES.get(approval.stage, approval.stage)} Approval',
            recipients=[approver.email],
            html=html_body,
            body=text_body
        )
        
        mail.send(msg)
        
        # Mark notification as sent
        approval.notification_sent = True
        db.session.commit()
        
        logger.info(f"Approval notification sent to {approver.email} for approval {approval_id}")
        return {'status': 'success', 'approval_id': approval_id}
        
    except Exception as e:
        logger.error(f"Failed to send approval notification: {e}")
        return {'status': 'failed', 'error': str(e)}


# ============================================
# Booking Management Tasks
# ============================================

@celery_app.task(bind=True, name='venue.auto_cancel_expired_bookings')
def auto_cancel_expired_bookings(self):
    """
    Auto-cancel bookings that haven't been approved within timeout period
    """
    logger.info("Checking for expired pending bookings...")
    
    try:
        now = datetime.utcnow()
        timeout_hours = current_app.config.get('APPROVAL_TIMEOUT_HOURS', 48)
        
        # Find pending approvals older than timeout
        expired_approvals = VenueApprovalRequest.query.filter(
            VenueApprovalRequest.status == 'pending',
            VenueApprovalRequest.request_date < now - timedelta(hours=timeout_hours)
        ).all()
        
        cancelled_count = 0
        
        for approval in expired_approvals:
            booking = approval.booking
            
            # Cancel the booking
            booking.status = BookingStatus.CANCELLED
            booking.rejection_reason = f"Auto-cancelled: No response within {timeout_hours} hours"
            booking.rejection_stage = approval.stage
            
            # Update approval status
            approval.status = 'rejected'
            approval.comments = "Auto-cancelled due to timeout"
            approval.response_date = now
            
            cancelled_count += 1
            logger.info(f"Auto-cancelled booking {booking.id} - no {approval.stage} approval")
        
        db.session.commit()
        
        return {
            'status': 'completed',
            'cancelled': cancelled_count,
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Auto-cancel task failed: {e}")
        return {'status': 'failed', 'error': str(e)}


@celery_app.task(bind=True, name='venue.mark_completed_bookings')
def mark_completed_bookings(self):
    """
    Mark bookings as completed after end time
    """
    logger.info("Marking completed bookings...")
    
    try:
        now = datetime.utcnow()
        
        # Find bookings that have ended
        completed_bookings = VenueBooking.query.filter(
            VenueBooking.status.in_(['approved', 'confirmed']),
            VenueBooking.end_time < now
        ).all()
        
        completed_count = 0
        
        for booking in completed_bookings:
            booking.status = BookingStatus.COMPLETED
            completed_count += 1
            logger.info(f"Marked booking {booking.id} as completed")
        
        db.session.commit()
        
        return {
            'status': 'completed',
            'marked': completed_count,
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Mark completed task failed: {e}")
        return {'status': 'failed', 'error': str(e)}


@celery_app.task(bind=True, name='venue.send_checkin_reminders')
def send_checkin_reminders(self):
    """
    Send check-in reminders to users with upcoming bookings
    """
    logger.info("Sending check-in reminders...")
    
    try:
        now = datetime.utcnow()
        upcoming_window = now + timedelta(hours=2)
        
        upcoming_bookings = VenueBooking.query.filter(
            VenueBooking.status.in_(['approved', 'confirmed']),
            VenueBooking.start_time > now,
            VenueBooking.start_time <= upcoming_window
        ).all()
        
        sent_count = 0
        
        for booking in upcoming_bookings:
            try:
                NotificationService.send_checkin_reminder(booking.id)
                sent_count += 1
                logger.info(f"Check-in reminder sent for booking {booking.id}")
                
            except Exception as e:
                logger.error(f"Failed to send check-in reminder for booking {booking.id}: {e}")
        
        return {
            'status': 'completed',
            'sent': sent_count,
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Check-in reminders task failed: {e}")
        return {'status': 'failed', 'error': str(e)}


# ============================================
# Maintenance & Cleanup Tasks
# ============================================

@celery_app.task(bind=True, name='venue.cleanup_old_bookings')
def cleanup_old_bookings(self, days=90):
    """
    Archive or delete old bookings
    """
    logger.info(f"Cleaning up bookings older than {days} days...")
    
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Find old completed/cancelled bookings
        old_bookings = VenueBooking.query.filter(
            VenueBooking.status.in_(['completed', 'cancelled', 'rejected']),
            VenueBooking.end_time < cutoff_date
        ).all()
        
        archived_count = 0
        
        for booking in old_bookings:
            # Mark as archived (soft delete)
            # In production, you might move to an archive table
            logger.info(f"Archiving booking {booking.id} - {booking.title}")
            archived_count += 1
        
        return {
            'status': 'completed',
            'archived': archived_count,
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Cleanup task failed: {e}")
        return {'status': 'failed', 'error': str(e)}


@celery_app.task(bind=True, name='venue.update_maintenance_slots')
def update_maintenance_slots(self):
    """
    Update maintenance slot statuses
    """
    logger.info("Updating maintenance slots...")
    
    try:
        now = datetime.utcnow()
        
        # Start maintenance slots that are scheduled
        upcoming_maintenance = VenueMaintenanceSlot.query.filter(
            VenueMaintenanceSlot.status == 'scheduled',
            VenueMaintenanceSlot.start_time <= now,
            VenueMaintenanceSlot.end_time > now
        ).all()
        
        started_count = 0
        for slot in upcoming_maintenance:
            slot.status = 'in_progress'
            started_count += 1
            logger.info(f"Started maintenance for venue {slot.venue_id}")
        
        # Complete maintenance slots that have ended
        ongoing_maintenance = VenueMaintenanceSlot.query.filter(
            VenueMaintenanceSlot.status == 'in_progress',
            VenueMaintenanceSlot.end_time <= now
        ).all()
        
        completed_count = 0
        for slot in ongoing_maintenance:
            slot.status = 'completed'
            completed_count += 1
            logger.info(f"Completed maintenance for venue {slot.venue_id}")
        
        db.session.commit()
        
        return {
            'status': 'completed',
            'started': started_count,
            'completed': completed_count,
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Maintenance update task failed: {e}")
        return {'status': 'failed', 'error': str(e)}


@celery_app.task(bind=True, name='venue.cleanup_expired_approvals')
def cleanup_expired_approvals(self):
    """
    Clean up expired approval requests (older than 30 days)
    """
    logger.info("Cleaning up expired approvals...")
    
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=30)
        
        expired_approvals = VenueApprovalRequest.query.filter(
            VenueApprovalRequest.status.in_(['approved', 'rejected']),
            VenueApprovalRequest.response_date < cutoff_date
        ).all()
        
        deleted_count = 0
        
        for approval in expired_approvals:
            db.session.delete(approval)
            deleted_count += 1
        
        db.session.commit()
        
        logger.info(f"Cleaned up {deleted_count} expired approvals")
        
        return {
            'status': 'completed',
            'deleted': deleted_count,
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Expired approvals cleanup failed: {e}")
        return {'status': 'failed', 'error': str(e)}


# ============================================
# Analytics & Reporting Tasks
# ============================================

@celery_app.task(bind=True, name='venue.generate_daily_report')
def generate_daily_report(self):
    """
    Generate daily venue usage report
    """
    logger.info("Generating daily venue usage report...")
    
    try:
        today = datetime.utcnow().date()
        start_of_day = datetime.combine(today, datetime.min.time())
        end_of_day = datetime.combine(today, datetime.max.time())
        
        # Get today's statistics
        total_bookings = VenueBooking.query.filter(
            VenueBooking.start_time >= start_of_day,
            VenueBooking.start_time <= end_of_day
        ).count()
        
        approved_bookings = VenueBooking.query.filter(
            VenueBooking.start_time >= start_of_day,
            VenueBooking.start_time <= end_of_day,
            VenueBooking.status == 'confirmed'
        ).count()
        
        pending_approvals = VenueApprovalRequest.query.filter(
            VenueApprovalRequest.status == 'pending'
        ).count()
        
        # Get venue usage
        venue_usage = []
        venues = Venue.query.all()
        
        for venue in venues:
            booking_count = VenueBooking.query.filter(
                VenueBooking.venue_id == venue.id,
                VenueBooking.start_time >= start_of_day,
                VenueBooking.start_time <= end_of_day
            ).count()
            
            venue_usage.append({
                'venue_id': venue.id,
                'venue_name': venue.name,
                'booking_count': booking_count
            })
        
        report_data = {
            'date': today.isoformat(),
            'total_bookings': total_bookings,
            'approved_bookings': approved_bookings,
            'pending_approvals': pending_approvals,
            'venue_usage': venue_usage
        }
        
        # Send report to admins
        send_daily_report_email.delay(report_data)
        
        logger.info(f"Daily report generated: {total_bookings} bookings")
        
        return {
            'status': 'completed',
            'report': report_data,
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Daily report generation failed: {e}")
        return {'status': 'failed', 'error': str(e)}


@celery_app.task(bind=True, name='venue.send_daily_report_email')
def send_daily_report_email(self, report_data):
    """Send daily report email to admins"""
    from flask_mail import Message
    
    try:
        admin_emails = User.query.filter_by(role='admin').with_entities(User.email).all()
        admin_emails = [email[0] for email in admin_emails if email[0]]
        
        if not admin_emails:
            logger.warning("No admin emails found")
            return {'status': 'completed', 'recipients': 0}
        
        context = {
            'report': report_data,
            'date': report_data['date']
        }
        
        html_body = render_template('emails/daily_venue_report.html', **context)
        text_body = render_template('emails/daily_venue_report.txt', **context)
        
        msg = Message(
            subject=f"Daily Venue Report - {report_data['date']}",
            recipients=admin_emails,
            html=html_body,
            body=text_body
        )
        
        mail.send(msg)
        
        logger.info(f"Daily report sent to {len(admin_emails)} admins")
        
        return {'status': 'success', 'recipients': len(admin_emails)}
        
    except Exception as e:
        logger.error(f"Failed to send daily report email: {e}")
        return {'status': 'failed', 'error': str(e)}


# ============================================
# Conflict Resolution Tasks
# ============================================

@celery_app.task(bind=True, name='venue.resolve_booking_conflicts')
def resolve_booking_conflicts(self):
    """
    Detect and resolve booking conflicts based on priority
    Academic > Cultural > Practice
    """
    logger.info("Checking for booking conflicts...")
    
    try:
        now = datetime.utcnow()
        upcoming_window = now + timedelta(days=7)
        
        # Get all approved/confirmed bookings for the next 7 days
        bookings = VenueBooking.query.filter(
            VenueBooking.status.in_(['approved', 'confirmed']),
            VenueBooking.start_time >= now,
            VenueBooking.start_time <= upcoming_window
        ).all()
        
        conflicts = []
        resolved = 0
        
        # Group by venue
        bookings_by_venue = {}
        for booking in bookings:
            if booking.venue_id not in bookings_by_venue:
                bookings_by_venue[booking.venue_id] = []
            bookings_by_venue[booking.venue_id].append(booking)
        
        # Check for conflicts in each venue
        for venue_id, venue_bookings in bookings_by_venue.items():
            # Sort by start time
            venue_bookings.sort(key=lambda x: x.start_time)
            
            for i in range(len(venue_bookings)):
                for j in range(i + 1, len(venue_bookings)):
                    b1 = venue_bookings[i]
                    b2 = venue_bookings[j]
                    
                    # Check for overlap
                    if b1.start_time < b2.end_time and b2.start_time < b1.end_time:
                        conflicts.append({
                            'booking1': b1.id,
                            'booking2': b2.id,
                            'venue_id': venue_id
                        })
                        
                        # Resolve based on priority (lower number = higher priority)
                        if b1.priority < b2.priority:
                            b2.status = BookingStatus.CANCELLED
                            b2.rejection_reason = f"Cancelled due to conflict with higher priority booking: {b1.title}"
                            resolved += 1
                            logger.info(f"Resolved conflict: {b2.title} cancelled")
                        elif b2.priority < b1.priority:
                            b1.status = BookingStatus.CANCELLED
                            b1.rejection_reason = f"Cancelled due to conflict with higher priority booking: {b2.title}"
                            resolved += 1
                            logger.info(f"Resolved conflict: {b1.title} cancelled")
        
        db.session.commit()
        
        logger.info(f"Conflict check completed: {len(conflicts)} conflicts found, {resolved} resolved")
        
        return {
            'status': 'completed',
            'conflicts_found': len(conflicts),
            'resolved': resolved,
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Conflict resolution task failed: {e}")
        return {'status': 'failed', 'error': str(e)}


# ============================================
# Priority Management Tasks
# ============================================

@celery_app.task(bind=True, name='venue.auto_escalate_priorities')
def auto_escalate_priorities(self):
    """
    Automatically escalate priorities for delayed approvals
    """
    logger.info("Auto-escalating priorities for delayed approvals...")
    
    try:
        escalated = PriorityService.auto_escalate_delayed_approvals(24)
        
        return {
            'status': 'completed',
            'escalated': escalated,
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Auto-escalate priorities task failed: {e}")
        return {'status': 'failed', 'error': str(e)}


# ============================================
# Scheduled Tasks (to be called by Celery Beat)
# ============================================

@celery_app.task(bind=True, name='venue.scheduled_hourly_tasks')
def scheduled_hourly_tasks(self):
    """Run all hourly scheduled tasks"""
    logger.info("Running hourly scheduled tasks...")
    
    tasks = [
        send_booking_reminders.delay(),
        send_checkin_reminders.delay(),
        auto_cancel_expired_bookings.delay(),
        auto_escalate_priorities.delay()
    ]
    
    return {
        'status': 'initiated',
        'tasks': len(tasks),
        'timestamp': datetime.utcnow().isoformat()
    }


@celery_app.task(bind=True, name='venue.scheduled_daily_tasks')
def scheduled_daily_tasks(self):
    """Run all daily scheduled tasks"""
    logger.info("Running daily scheduled tasks...")
    
    tasks = [
        mark_completed_bookings.delay(),
        generate_daily_report.delay(),
        cleanup_old_bookings.delay(),
        update_maintenance_slots.delay(),
        resolve_booking_conflicts.delay()
    ]
    
    return {
        'status': 'initiated',
        'tasks': len(tasks),
        'timestamp': datetime.utcnow().isoformat()
    }


@celery_app.task(bind=True, name='venue.scheduled_weekly_tasks')
def scheduled_weekly_tasks(self):
    """Run all weekly scheduled tasks"""
    logger.info("Running weekly scheduled tasks...")
    
    tasks = [
        cleanup_expired_approvals.delay(),
        cleanup_old_bookings.delay(days=90)
    ]
    
    return {
        'status': 'initiated',
        'tasks': len(tasks),
        'timestamp': datetime.utcnow().isoformat()
    }


# ============================================
# Utility Functions
# ============================================

def get_task_status(task_id):
    """Get status of a Celery task"""
    from celery.result import AsyncResult
    
    task = AsyncResult(task_id, app=celery_app)
    
    if task.pending:
        return {'status': 'pending'}
    elif task.failed():
        return {'status': 'failed', 'error': str(task.info)}
    elif task.successful():
        return {'status': 'completed', 'result': task.result}
    else:
        return {'status': 'processing'}