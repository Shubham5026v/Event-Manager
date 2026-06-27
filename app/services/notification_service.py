"""
Notification Service - Email and SMS Notifications
Handles booking confirmations, approval requests, reminders, and alerts
"""

from datetime import datetime, timedelta
from flask import current_app, render_template
from flask_mail import Message
from app import db, mail
from app.models import VenueBooking, BookingStatus
from app.models import User
from app.models import VenueApprovalRequest

class NotificationService:
    """
    Service class for sending notifications
    Handles email and SMS notifications for bookings, approvals, and reminders
    """
    
    # Notification types
    NOTIFICATION_TYPES = {
        'booking_confirmation': 'Booking Confirmation',
        'booking_reminder': 'Booking Reminder',
        'approval_request': 'Approval Request',
        'approval_response': 'Approval Response',
        'booking_cancellation': 'Booking Cancellation',
        'checkin_reminder': 'Check-in Reminder',
        'shortlist_notification': 'Shortlist Notification'
    }
    
    @classmethod
    def send_booking_confirmation(cls, booking_id):
        """
        Send booking confirmation email to the requester
        
        Args:
            booking_id: ID of the booking
            
        Returns:
            bool: True if sent successfully
        """
        try:
            booking = VenueBooking.query.get(booking_id)
            if not booking:
                current_app.logger.error(f"Booking {booking_id} not found for confirmation")
                return False
            
            user = User.query.get(booking.created_by)
            if not user or not user.email:
                current_app.logger.error(f"User {booking.created_by} has no email")
                return False
            
            context = {
                'booking': booking,
                'venue': booking.venue,
                'user': user,
                'booking_url': f"/bookings/{booking.id}",
                'cancel_url': f"/bookings/{booking.id}/cancel",
                'approval_status': booking.get_current_approval_stage()
            }
            
            html_body = render_template('emails/booking_confirmation.html', **context)
            text_body = render_template('emails/booking_confirmation.txt', **context)
            
            msg = Message(
                subject=f"Booking Confirmation: {booking.title}",
                recipients=[user.email],
                html=html_body,
                body=text_body
            )
            
            mail.send(msg)
            current_app.logger.info(f"Booking confirmation sent to {user.email} for booking {booking.id}")
            return True
            
        except Exception as e:
            current_app.logger.error(f"Failed to send booking confirmation: {e}")
            return False
    
    @classmethod
    def send_approval_notification(cls, approval_id):
        """
        Send approval request notification to the approver
        
        Args:
            approval_id: ID of the approval request
            
        Returns:
            bool: True if sent successfully
        """
        try:
            approval = VenueApprovalRequest.query.get(approval_id)
            if not approval:
                current_app.logger.error(f"Approval {approval_id} not found")
                return False
            
            booking = approval.booking
            approver = User.query.get(approval.approver_id)
            
            if not approver or not approver.email:
                current_app.logger.error(f"Approver {approval.approver_id} has no email")
                return False
            
            requester = User.query.get(booking.created_by)
            
            context = {
                'approval': approval,
                'booking': booking,
                'venue': booking.venue,
                'requester': requester,
                'stage': approval.stage,
                'stage_name': cls._get_stage_name(approval.stage),
                'approval_url': f"/approvals/{approval.id}",
                'booking_url': f"/bookings/{booking.id}"
            }
            
            html_body = render_template('emails/approval_notification.html', **context)
            text_body = render_template('emails/approval_notification.txt', **context)
            
            msg = Message(
                subject=f"Action Required: {booking.title} - {cls._get_stage_name(approval.stage)} Approval",
                recipients=[approver.email],
                html=html_body,
                body=text_body
            )
            
            mail.send(msg)
            
            # Mark notification as sent
            approval.notification_sent = True
            db.session.commit()
            
            current_app.logger.info(f"Approval notification sent to {approver.email} for approval {approval_id}")
            return True
            
        except Exception as e:
            current_app.logger.error(f"Failed to send approval notification: {e}")
            return False
    
    @classmethod
    def send_approval_response_notification(cls, approval_id, approved, comments=None):
        """
        Send approval response notification to the requester
        
        Args:
            approval_id: ID of the approval request
            approved: Boolean indicating if approved
            comments: Optional comments from approver
            
        Returns:
            bool: True if sent successfully
        """
        try:
            approval = VenueApprovalRequest.query.get(approval_id)
            if not approval:
                current_app.logger.error(f"Approval {approval_id} not found")
                return False
            
            booking = approval.booking
            requester = User.query.get(booking.created_by)
            
            if not requester or not requester.email:
                current_app.logger.error(f"Requester {booking.created_by} has no email")
                return False
            
            approver = User.query.get(approval.approver_id)
            
            context = {
                'booking': booking,
                'venue': booking.venue,
                'approved': approved,
                'stage': approval.stage,
                'stage_name': cls._get_stage_name(approval.stage),
                'approver_name': approver.username if approver else 'System',
                'comments': comments or approval.comments,
                'booking_url': f"/bookings/{booking.id}"
            }
            
            status_text = "Approved" if approved else "Rejected"
            html_body = render_template('emails/approval_response.html', **context)
            text_body = render_template('emails/approval_response.txt', **context)
            
            msg = Message(
                subject=f"{status_text}: {booking.title} - {cls._get_stage_name(approval.stage)}",
                recipients=[requester.email],
                html=html_body,
                body=text_body
            )
            
            mail.send(msg)
            current_app.logger.info(f"Approval response sent to {requester.email} for booking {booking.id}")
            return True
            
        except Exception as e:
            current_app.logger.error(f"Failed to send approval response: {e}")
            return False
    
    @classmethod
    def send_booking_reminder(cls, booking_id, reminder_type='hour_before'):
        """
        Send booking reminder email
        
        Args:
            booking_id: ID of the booking
            reminder_type: Type of reminder (day_before, hour_before, 15min_before)
            
        Returns:
            bool: True if sent successfully
        """
        try:
            booking = VenueBooking.query.get(booking_id)
            if not booking:
                current_app.logger.error(f"Booking {booking_id} not found for reminder")
                return False
            
            user = User.query.get(booking.created_by)
            if not user or not user.email:
                current_app.logger.error(f"User {booking.created_by} has no email")
                return False
            
            reminder_messages = {
                'day_before': {
                    'subject': f'Reminder: {booking.title} Tomorrow',
                    'urgency': 'regular',
                    'time_text': 'tomorrow'
                },
                'hour_before': {
                    'subject': f'Upcoming: {booking.title} in 1 Hour',
                    'urgency': 'high',
                    'time_text': 'in 1 hour'
                },
                '15min_before': {
                    'subject': f'Starting Soon: {booking.title} in 15 Minutes',
                    'urgency': 'urgent',
                    'time_text': 'in 15 minutes'
                }
            }
            
            msg_info = reminder_messages.get(reminder_type, reminder_messages['hour_before'])
            
            context = {
                'booking': booking,
                'venue': booking.venue,
                'user': user,
                'reminder_type': reminder_type,
                'time_text': msg_info['time_text'],
                'booking_url': f"/bookings/{booking.id}",
                'check_in_url': f"/bookings/{booking.id}/check-in",
                'venue_location': booking.venue.building or booking.venue.name
            }
            
            html_body = render_template('emails/booking_reminder.html', **context)
            text_body = render_template('emails/booking_reminder.txt', **context)
            
            msg = Message(
                subject=msg_info['subject'],
                recipients=[user.email],
                html=html_body,
                body=text_body
            )
            
            mail.send(msg)
            current_app.logger.info(f"Booking reminder sent to {user.email} for booking {booking.id}")
            return True
            
        except Exception as e:
            current_app.logger.error(f"Failed to send booking reminder: {e}")
            return False
    
    @classmethod
    def send_booking_cancellation(cls, booking_id, reason=None):
        """
        Send booking cancellation notification
        
        Args:
            booking_id: ID of the booking
            reason: Reason for cancellation
            
        Returns:
            bool: True if sent successfully
        """
        try:
            booking = VenueBooking.query.get(booking_id)
            if not booking:
                current_app.logger.error(f"Booking {booking_id} not found for cancellation")
                return False
            
            user = User.query.get(booking.created_by)
            if not user or not user.email:
                current_app.logger.error(f"User {booking.created_by} has no email")
                return False
            
            context = {
                'booking': booking,
                'venue': booking.venue,
                'user': user,
                'reason': reason or booking.rejection_reason,
                'cancelled_at': datetime.utcnow(),
                'booking_url': f"/bookings/{booking.id}"
            }
            
            html_body = render_template('emails/booking_cancellation.html', **context)
            text_body = render_template('emails/booking_cancellation.txt', **context)
            
            msg = Message(
                subject=f"Cancelled: {booking.title}",
                recipients=[user.email],
                html=html_body,
                body=text_body
            )
            
            mail.send(msg)
            current_app.logger.info(f"Booking cancellation sent to {user.email} for booking {booking.id}")
            return True
            
        except Exception as e:
            current_app.logger.error(f"Failed to send booking cancellation: {e}")
            return False
    
    @classmethod
    def send_checkin_reminder(cls, booking_id):
        """
        Send check-in reminder for a booking
        
        Args:
            booking_id: ID of the booking
            
        Returns:
            bool: True if sent successfully
        """
        try:
            booking = VenueBooking.query.get(booking_id)
            if not booking:
                current_app.logger.error(f"Booking {booking_id} not found for check-in reminder")
                return False
            
            user = User.query.get(booking.created_by)
            if not user or not user.email:
                current_app.logger.error(f"User {booking.created_by} has no email")
                return False
            
            context = {
                'booking': booking,
                'venue': booking.venue,
                'user': user,
                'check_in_url': f"/bookings/{booking.id}/check-in",
                'venue_location': booking.venue.building or booking.venue.name,
                'qr_code_url': f"/bookings/{booking.id}/qr-code"
            }
            
            html_body = render_template('emails/checkin_reminder.html', **context)
            text_body = render_template('emails/checkin_reminder.txt', **context)
            
            msg = Message(
                subject=f"Ready to Check In: {booking.title}",
                recipients=[user.email],
                html=html_body,
                body=text_body
            )
            
            mail.send(msg)
            current_app.logger.info(f"Check-in reminder sent to {user.email} for booking {booking.id}")
            return True
            
        except Exception as e:
            current_app.logger.error(f"Failed to send check-in reminder: {e}")
            return False
    
    @classmethod
    def send_bulk_booking_reminders(cls, reminder_type='hour_before'):
        """
        Send bulk booking reminders for upcoming bookings
        
        Args:
            reminder_type: Type of reminder to send
            
        Returns:
            dict: Summary of sent reminders
        """
        now = datetime.utcnow()
        sent_count = 0
        failed_count = 0
        
        if reminder_type == 'day_before':
            reminder_time = now + timedelta(hours=24)
        elif reminder_type == 'hour_before':
            reminder_time = now + timedelta(hours=1)
        elif reminder_type == '15min_before':
            reminder_time = now + timedelta(minutes=15)
        else:
            reminder_time = now + timedelta(hours=1)
        
        reminder_window_start = reminder_time - timedelta(minutes=5)
        reminder_window_end = reminder_time + timedelta(minutes=5)
        
        bookings = VenueBooking.query.filter(
            VenueBooking.start_time >= reminder_window_start,
            VenueBooking.start_time <= reminder_window_end,
            VenueBooking.status.in_(['approved', 'confirmed'])
        ).all()
        
        for booking in bookings:
            if cls.send_booking_reminder(booking.id, reminder_type):
                sent_count += 1
            else:
                failed_count += 1
        
        return {
            'reminder_type': reminder_type,
            'sent': sent_count,
            'failed': failed_count,
            'total': len(bookings)
        }
    
    @classmethod
    def send_daily_summary(cls, venue_id=None):
        """
        Send daily summary of bookings to admins
        
        Args:
            venue_id: Optional venue ID for specific venue summary
            
        Returns:
            bool: True if sent successfully
        """
        try:
            today = datetime.utcnow().date()
            tomorrow = today + timedelta(days=1)
            
            start_of_day = datetime.combine(today, datetime.min.time())
            end_of_day = datetime.combine(tomorrow, datetime.min.time())
            
            query = VenueBooking.query.filter(
                VenueBooking.start_time >= start_of_day,
                VenueBooking.start_time < end_of_day,
                VenueBooking.status.in_(['approved', 'confirmed', 'pending_faculty', 'pending_admin', 'pending_security'])
            )
            
            if venue_id:
                query = query.filter_by(venue_id=venue_id)
            
            bookings = query.all()
            
            # Get admin emails
            admin_emails = User.query.filter_by(role='admin').with_entities(User.email).all()
            admin_emails = [email[0] for email in admin_emails if email[0]]
            
            if not admin_emails:
                current_app.logger.warning("No admin emails found for daily summary")
                return False
            
            # Group bookings by status
            approved = [b for b in bookings if b.status == BookingStatus.CONFIRMED]
            pending = [b for b in bookings if b.status not in [BookingStatus.CONFIRMED, BookingStatus.COMPLETED]]
            
            context = {
                'date': today,
                'total_bookings': len(bookings),
                'approved_count': len(approved),
                'pending_count': len(pending),
                'approved_bookings': approved,
                'pending_bookings': pending,
                'venue_name': Venue.query.get(venue_id).name if venue_id else 'All Venues'
            }
            
            html_body = render_template('emails/daily_booking_summary.html', **context)
            text_body = render_template('emails/daily_booking_summary.txt', **context)
            
            msg = Message(
                subject=f"Daily Booking Summary - {today.strftime('%B %d, %Y')}",
                recipients=admin_emails,
                html=html_body,
                body=text_body
            )
            
            mail.send(msg)
            current_app.logger.info(f"Daily summary sent to {len(admin_emails)} admins")
            return True
            
        except Exception as e:
            current_app.logger.error(f"Failed to send daily summary: {e}")
            return False
    
    @classmethod
    def send_sms_notification(cls, phone_number, message):
        """
        Send SMS notification (placeholder - integrate with SMS provider)
        
        Args:
            phone_number: Recipient phone number
            message: SMS message content
            
        Returns:
            bool: True if sent successfully
        """
        try:
            # This is a placeholder for SMS provider integration
            # Example: Twilio, AWS SNS, etc.
            current_app.logger.info(f"SMS would be sent to {phone_number}: {message[:50]}...")
            
            # Uncomment when SMS provider is configured:
            # from twilio.rest import Client
            # client = Client(account_sid, auth_token)
            # client.messages.create(
            #     body=message,
            #     from_=twilio_phone_number,
            #     to=phone_number
            # )
            
            return True
            
        except Exception as e:
            current_app.logger.error(f"Failed to send SMS: {e}")
            return False
    
    @classmethod
    def send_booking_confirmation_sms(cls, booking_id):
        """
        Send booking confirmation SMS
        
        Args:
            booking_id: ID of the booking
            
        Returns:
            bool: True if sent successfully
        """
        try:
            booking = VenueBooking.query.get(booking_id)
            if not booking:
                return False
            
            user = User.query.get(booking.created_by)
            if not user or not user.phone:
                return False
            
            message = f"EventX: Booking confirmed for {booking.title} on {booking.start_time.strftime('%b %d, %H:%M')} at {booking.venue.name}"
            
            return cls.send_sms_notification(user.phone, message)
            
        except Exception as e:
            current_app.logger.error(f"Failed to send booking confirmation SMS: {e}")
            return False
    
    @classmethod
    def _get_stage_name(cls, stage):
        """Get display name for approval stage"""
        stage_names = {
            'faculty': 'Faculty',
            'admin': 'Admin',
            'security': 'Security'
        }
        return stage_names.get(stage, stage.capitalize())