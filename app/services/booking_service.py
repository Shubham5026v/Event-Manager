"""
Booking Service - Core Booking Business Logic
Handles booking creation, conflict resolution, availability checking, and priority-based scheduling
"""

from datetime import datetime, timedelta
from flask import current_app
from app import db
from app.models import VenueBooking, BookingStatus, BookingPriority
from app.models import Venue, VenueStatus
from app.models import User
from app.services.priority_service import PriorityService
from app.services.approval_service import ApprovalService

class BookingService:
    """
    Service class for managing venue bookings
    Handles booking creation, modification, cancellation, and conflict resolution
    """
    
    @classmethod
    def create_booking(cls, data, user_id):
        """
        Create a new booking with validation, priority handling, and approval initiation
        
        Args:
            data: Dictionary with booking data (title, venue_id, start_time, end_time, etc.)
            user_id: ID of the user creating the booking
            
        Returns:
            VenueBooking: Created booking object
            
        Raises:
            ValueError: If validation fails
        """
        try:
            # Validate required fields
            cls._validate_booking_data(data)
            
            # Get venue and check if exists
            venue = Venue.query.get(data['venue_id'])
            if not venue:
                raise ValueError("Venue not found")
            
            # Check if venue is active
            if venue.status != VenueStatus.ACTIVE:
                raise ValueError(f"Venue is not available (Status: {venue.status.value})")
            
            # Check venue availability
            if not venue.is_available(data['start_time'], data['end_time']):
                raise ValueError("Venue is not available for the selected time slot")
            
            # Check against operating hours
            if not cls._is_within_operating_hours(venue, data['start_time'], data['end_time']):
                raise ValueError("Selected time is outside venue operating hours")
            
            # Check booking window limits
            if not cls._is_within_booking_window(data['start_time']):
                raise ValueError("Bookings must be made at least 24 hours in advance")
            
            # Calculate priority based on event type (Academic > Cultural > Practice)
            priority = PriorityService.get_priority(data.get('event_type', 'practice'))
            
            # Check for conflicts with higher priority bookings
            conflict = cls._check_priority_conflict(venue.id, data['start_time'], data['end_time'], priority)
            if conflict:
                raise ValueError(f"Conflict with higher priority booking: {conflict.title}")
            
            # Create booking object
            booking = VenueBooking(
                title=data['title'],
                description=data.get('description', ''),
                event_type=data.get('event_type', 'practice'),
                venue_id=data['venue_id'],
                start_time=data['start_time'],
                end_time=data['end_time'],
                setup_time=data.get('setup_time', 30),
                cleanup_time=data.get('cleanup_time', 30),
                expected_attendees=data.get('expected_attendees', 0),
                priority=priority,
                requirements=data.get('requirements', {}),
                special_requests=data.get('special_requests', ''),
                created_by=user_id,
                status=BookingStatus.PENDING_FACULTY
            )
            
            db.session.add(booking)
            db.session.commit()
            
            # Initiate approval workflow (Faculty → Admin → Security)
            ApprovalService.initiate_approval(booking.id)
            
            current_app.logger.info(f"Booking created: {booking.id} - {booking.title}")
            
            return booking
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Booking creation failed: {e}")
            raise
    
    @classmethod
    def update_booking(cls, booking_id, data, user_id):
        """
        Update an existing booking
        
        Args:
            booking_id: ID of the booking to update
            data: Dictionary with updated booking data
            user_id: ID of the user making the update
            
        Returns:
            VenueBooking: Updated booking object
        """
        try:
            booking = VenueBooking.query.get(booking_id)
            if not booking:
                raise ValueError("Booking not found")
            
            # Check if booking can be modified
            if booking.status not in [BookingStatus.DRAFT, BookingStatus.PENDING_FACULTY]:
                raise ValueError("Booking cannot be modified at this stage")
            
            # Check permissions
            if booking.created_by != user_id:
                user = User.query.get(user_id)
                if not user or user.role != 'admin':
                    raise PermissionError("You don't have permission to update this booking")
            
            # Update fields if provided
            if 'title' in data:
                booking.title = data['title']
            if 'description' in data:
                booking.description = data['description']
            if 'event_type' in data:
                booking.event_type = data['event_type']
                booking.priority = PriorityService.get_priority(data['event_type'])
            if 'venue_id' in data:
                new_venue = Venue.query.get(data['venue_id'])
                if not new_venue:
                    raise ValueError("Venue not found")
                
                start = data.get('start_time', booking.start_time)
                end = data.get('end_time', booking.end_time)
                if not new_venue.is_available(start, end, booking_id):
                    raise ValueError("Selected venue is not available for the time slot")
                booking.venue_id = data['venue_id']
            
            if 'start_time' in data:
                booking.start_time = data['start_time']
            if 'end_time' in data:
                booking.end_time = data['end_time']
            if 'setup_time' in data:
                booking.setup_time = data['setup_time']
            if 'cleanup_time' in data:
                booking.cleanup_time = data['cleanup_time']
            if 'expected_attendees' in data:
                booking.expected_attendees = data['expected_attendees']
            if 'requirements' in data:
                booking.requirements = data['requirements']
            if 'special_requests' in data:
                booking.special_requests = data['special_requests']
            
            # Validate updated time slot
            if not booking.venue.is_available(booking.start_time, booking.end_time, booking_id):
                raise ValueError("Updated time slot is not available")
            
            booking.updated_at = datetime.utcnow()
            db.session.commit()
            
            current_app.logger.info(f"Booking updated: {booking.id}")
            return booking
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Booking update failed: {e}")
            raise
    
    @classmethod
    def cancel_booking(cls, booking_id, user_id, reason=None):
        """
        Cancel a booking
        
        Args:
            booking_id: ID of the booking to cancel
            user_id: ID of the user cancelling
            reason: Reason for cancellation
            
        Returns:
            VenueBooking: Cancelled booking object
        """
        try:
            booking = VenueBooking.query.get(booking_id)
            if not booking:
                raise ValueError("Booking not found")
            
            if not booking.can_cancel():
                raise ValueError("Booking cannot be cancelled at this stage")
            
            # Check permissions
            if booking.created_by != user_id:
                user = User.query.get(user_id)
                if not user or user.role not in ['admin', 'security']:
                    raise PermissionError("You don't have permission to cancel this booking")
            
            old_status = booking.status
            booking.status = BookingStatus.CANCELLED
            booking.rejection_reason = reason or "Cancelled by user"
            booking.updated_at = datetime.utcnow()
            
            # Cancel pending approvals
            from app.models import VenueApprovalRequest
            pending_approvals = VenueApprovalRequest.query.filter_by(
                booking_id=booking_id,
                status='pending'
            ).all()
            
            for approval in pending_approvals:
                approval.status = 'cancelled'
                approval.comments = f"Cancelled due to booking cancellation: {reason}"
            
            # Log history
            from app.models import VenueBookingHistory
            history = VenueBookingHistory(
                booking_id=booking_id,
                action='cancelled',
                old_status=old_status.value,
                new_status=BookingStatus.CANCELLED.value,
                comment=reason,
                performed_by=user_id
            )
            db.session.add(history)
            db.session.commit()
            
            current_app.logger.info(f"Booking cancelled: {booking.id} by user {user_id}")
            return booking
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Booking cancellation failed: {e}")
            raise
    
    @classmethod
    def get_upcoming_bookings(cls, user_id, days=7):
        """Get upcoming bookings for a user"""
        now = datetime.utcnow()
        cutoff = now + timedelta(days=days)
        
        bookings = VenueBooking.query.filter(
            VenueBooking.created_by == user_id,
            VenueBooking.start_time >= now,
            VenueBooking.start_time <= cutoff,
            VenueBooking.status.in_(['approved', 'confirmed'])
        ).order_by(VenueBooking.start_time).all()
        
        return bookings
    
    @classmethod
    def get_venue_bookings(cls, venue_id, start_date=None, end_date=None):
        """Get all bookings for a venue within date range"""
        if not start_date:
            start_date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        if not end_date:
            end_date = start_date + timedelta(days=30)
        
        bookings = VenueBooking.query.filter(
            VenueBooking.venue_id == venue_id,
            VenueBooking.start_time >= start_date,
            VenueBooking.end_time <= end_date,
            VenueBooking.status.in_(['approved', 'confirmed'])
        ).order_by(VenueBooking.start_time).all()
        
        return bookings
    
    @classmethod
    def check_availability(cls, venue_id, start_time, end_time, exclude_booking_id=None):
        """Check if a venue is available for a time slot"""
        venue = Venue.query.get(venue_id)
        if not venue:
            return False
        return venue.is_available(start_time, end_time, exclude_booking_id)
    
    @classmethod
    def get_available_venues(cls, start_time, end_time, venue_type=None, capacity_needed=None):
        """Get all available venues for a time slot"""
        query = Venue.query.filter(Venue.status == VenueStatus.ACTIVE)
        
        if venue_type:
            query = query.filter(Venue.type == venue_type)
        if capacity_needed:
            query = query.filter(Venue.capacity >= capacity_needed)
        
        venues = query.all()
        
        available = []
        for venue in venues:
            if venue.is_available(start_time, end_time):
                available.append(venue)
        
        return available
    
    @classmethod
    def get_alternative_venues(cls, venue_id, start_time, end_time, limit=5):
        """Get alternative venues for a time slot"""
        original_venue = Venue.query.get(venue_id)
        if not original_venue:
            return []
        
        # Get venues of same type with similar capacity
        capacity_range = original_venue.capacity * 0.2
        min_capacity = max(0, original_venue.capacity - capacity_range)
        max_capacity = original_venue.capacity + capacity_range
        
        venues = Venue.query.filter(
            Venue.id != venue_id,
            Venue.status == VenueStatus.ACTIVE,
            Venue.type == original_venue.type,
            Venue.capacity.between(min_capacity, max_capacity)
        ).limit(limit).all()
        
        alternatives = []
        for venue in venues:
            if venue.is_available(start_time, end_time):
                alternatives.append(venue)
        
        return alternatives
    
    @classmethod
    def get_booking_statistics(cls, venue_id=None, start_date=None, end_date=None):
        """Get booking statistics for a venue or overall"""
        if not start_date:
            start_date = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if not end_date:
            end_date = start_date + timedelta(days=30)
        
        query = VenueBooking.query.filter(
            VenueBooking.start_time >= start_date,
            VenueBooking.end_time <= end_date,
            VenueBooking.status.in_(['approved', 'confirmed', 'completed'])
        )
        
        if venue_id:
            query = query.filter_by(venue_id=venue_id)
        
        bookings = query.all()
        
        total_bookings = len(bookings)
        total_hours = sum((b.end_time - b.start_time).total_seconds() / 3600 for b in bookings)
        total_attendees = sum(b.expected_attendees or 0 for b in bookings)
        
        # Group by priority
        by_priority = {
            'academic': 0,
            'cultural': 0,
            'practice': 0
        }
        for booking in bookings:
            if booking.priority == BookingPriority.ACADEMIC.value:
                by_priority['academic'] += 1
            elif booking.priority == BookingPriority.CULTURAL.value:
                by_priority['cultural'] += 1
            else:
                by_priority['practice'] += 1
        
        return {
            'total_bookings': total_bookings,
            'total_hours': round(total_hours, 1),
            'total_attendees': total_attendees,
            'average_attendees': round(total_attendees / total_bookings, 1) if total_bookings > 0 else 0,
            'average_duration': round(total_hours / total_bookings, 1) if total_bookings > 0 else 0,
            'by_priority': by_priority,
            'period': {'start': start_date.isoformat(), 'end': end_date.isoformat()}
        }
    
    @classmethod
    def get_upcoming_reminders(cls, minutes_before=60):
        """Get bookings that need reminders"""
        now = datetime.utcnow()
        reminder_time = now + timedelta(minutes=minutes_before)
        reminder_window_start = reminder_time - timedelta(minutes=5)
        reminder_window_end = reminder_time + timedelta(minutes=5)
        
        bookings = VenueBooking.query.filter(
            VenueBooking.start_time >= reminder_window_start,
            VenueBooking.start_time <= reminder_window_end,
            VenueBooking.status.in_(['approved', 'confirmed'])
        ).all()
        
        return bookings
    
    @classmethod
    def check_in_booking(cls, booking_id, user_id):
        """Check in for a booking (security only)"""
        booking = VenueBooking.query.get(booking_id)
        if not booking:
            raise ValueError("Booking not found")
        
        if booking.status != BookingStatus.CONFIRMED:
            raise ValueError("Booking must be confirmed before check-in")
        
        booking.checked_in_at = datetime.utcnow()
        booking.security_check_in_by = user_id
        
        # Log history
        from app.models import VenueBookingHistory
        history = VenueBookingHistory(
            booking_id=booking_id,
            action='checked_in',
            old_status=booking.status.value,
            new_status=booking.status.value,
            performed_by=user_id
        )
        db.session.add(history)
        db.session.commit()
        
        return booking
    
    @classmethod
    def check_out_booking(cls, booking_id, user_id):
        """Check out from a booking (security only)"""
        booking = VenueBooking.query.get(booking_id)
        if not booking:
            raise ValueError("Booking not found")
        
        if not booking.checked_in_at:
            raise ValueError("Booking must be checked in first")
        
        booking.checked_out_at = datetime.utcnow()
        
        # Log history
        from app.models import VenueBookingHistory
        history = VenueBookingHistory(
            booking_id=booking_id,
            action='checked_out',
            old_status=booking.status.value,
            new_status=booking.status.value,
            performed_by=user_id
        )
        db.session.add(history)
        db.session.commit()
        
        return booking
    
    # ============================================
    # Private Helper Methods
    # ============================================
    
    @classmethod
    def _validate_booking_data(cls, data):
        """Validate booking data before creation"""
        required_fields = ['title', 'venue_id', 'start_time', 'end_time']
        for field in required_fields:
            if field not in data or not data[field]:
                raise ValueError(f"Missing required field: {field}")
        
        if data['start_time'] >= data['end_time']:
            raise ValueError("End time must be after start time")
        
        if data['start_time'] < datetime.utcnow():
            raise ValueError("Cannot book for past dates")
        
        duration = (data['end_time'] - data['start_time']).total_seconds() / 3600
        if duration < 0.5:
            raise ValueError("Minimum booking duration is 30 minutes")
        if duration > 12:
            raise ValueError("Maximum booking duration is 12 hours")
    
    @classmethod
    def _is_within_operating_hours(cls, venue, start_time, end_time):
        """Check if booking time is within venue operating hours"""
        if not venue.opens_at or not venue.closes_at:
            return True
        return start_time.time() >= venue.opens_at and end_time.time() <= venue.closes_at
    
    @classmethod
    def _is_within_booking_window(cls, start_time):
        """Check if booking is within allowed window"""
        now = datetime.utcnow()
        min_advance = timedelta(hours=24)
        max_advance = timedelta(days=90)
        return start_time >= now + min_advance and start_time <= now + max_advance
    
    @classmethod
    def _check_priority_conflict(cls, venue_id, start_time, end_time, new_priority):
        """Check for conflicts with higher priority bookings"""
        overlapping = VenueBooking.query.filter(
            VenueBooking.venue_id == venue_id,
            VenueBooking.status.in_(['approved', 'confirmed']),
            VenueBooking.start_time < end_time,
            VenueBooking.end_time > start_time
        ).all()
        
        for booking in overlapping:
            if booking.priority < new_priority:
                return booking
        return None