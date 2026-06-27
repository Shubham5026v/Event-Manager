"""
Priority Service - Booking Priority Management
Handles priority calculation, conflict resolution, and priority-based scheduling
Priority order: Academic (1) > Cultural (2) > Practice (3)
"""

from enum import IntEnum
from datetime import datetime
from flask import current_app
from app import db
from app.models import VenueBooking, BookingStatus, BookingPriority
from app.models import VenuePriorityRule, VenuePriorityOverride

class PriorityLevel(IntEnum):
    """Priority levels with numeric values (lower number = higher priority)"""
    ADMIN = 0          # Highest priority - Admin override
    ACADEMIC = 1       # Academic events (exams, lectures, seminars)
    CULTURAL = 2       # Cultural events (festivals, concerts)
    PRACTICE = 3       # Practice sessions (rehearsals, workshops)


class PriorityService:
    """
    Service class for managing booking priorities
    Handles priority calculation, conflict resolution, and priority-based rules
    Priority order: Academic > Cultural > Practice
    """
    
    # Priority mapping for event types
    EVENT_TYPE_PRIORITY = {
        'exam': PriorityLevel.ACADEMIC,
        'lecture': PriorityLevel.ACADEMIC,
        'seminar': PriorityLevel.ACADEMIC,
        'workshop': PriorityLevel.ACADEMIC,
        'conference': PriorityLevel.ACADEMIC,
        'festival': PriorityLevel.CULTURAL,
        'concert': PriorityLevel.CULTURAL,
        'drama': PriorityLevel.CULTURAL,
        'cultural_event': PriorityLevel.CULTURAL,
        'rehearsal': PriorityLevel.PRACTICE,
        'practice': PriorityLevel.PRACTICE,
        'training': PriorityLevel.PRACTICE,
        'meeting': PriorityLevel.PRACTICE,
        'default': PriorityLevel.PRACTICE
    }
    
    # Priority display names
    PRIORITY_NAMES = {
        PriorityLevel.ADMIN: 'Admin Priority (Highest)',
        PriorityLevel.ACADEMIC: 'Academic Priority (High)',
        PriorityLevel.CULTURAL: 'Cultural Priority (Medium)',
        PriorityLevel.PRACTICE: 'Practice Priority (Low)'
    }
    
    # Priority icons for UI
    PRIORITY_ICONS = {
        PriorityLevel.ADMIN: 'fa-bolt',
        PriorityLevel.ACADEMIC: 'fa-graduation-cap',
        PriorityLevel.CULTURAL: 'fa-music',
        PriorityLevel.PRACTICE: 'fa-leaf'
    }
    
    # Priority colors for UI
    PRIORITY_COLORS = {
        PriorityLevel.ADMIN: '#ff3366',
        PriorityLevel.ACADEMIC: '#2b6eff',
        PriorityLevel.CULTURAL: '#9b4dff',
        PriorityLevel.PRACTICE: '#00ff88'
    }
    
    @classmethod
    def get_priority(cls, event_type):
        """
        Get priority level for an event type
        Academic > Cultural > Practice
        
        Args:
            event_type: Type of event (e.g., 'academic', 'cultural', 'practice')
            
        Returns:
            int: Priority level (lower number = higher priority)
        """
        event_type_lower = event_type.lower() if event_type else 'default'
        priority = cls.EVENT_TYPE_PRIORITY.get(event_type_lower, PriorityLevel.PRACTICE)
        return priority.value
    
    @classmethod
    def get_priority_name(cls, priority_value):
        """Get display name for a priority level"""
        try:
            priority = PriorityLevel(priority_value)
            return cls.PRIORITY_NAMES.get(priority, 'Standard Priority')
        except ValueError:
            return 'Standard Priority'
    
    @classmethod
    def get_priority_icon(cls, priority_value):
        """Get icon class for a priority level"""
        try:
            priority = PriorityLevel(priority_value)
            return cls.PRIORITY_ICONS.get(priority, 'fa-flag')
        except ValueError:
            return 'fa-flag'
    
    @classmethod
    def get_priority_color(cls, priority_value):
        """Get color for a priority level"""
        try:
            priority = PriorityLevel(priority_value)
            return cls.PRIORITY_COLORS.get(priority, '#99aaff')
        except ValueError:
            return '#99aaff'
    
    @classmethod
    def compare_priority(cls, booking1, booking2):
        """
        Compare two bookings by priority
        Returns: -1 if booking1 has higher priority, 0 if equal, 1 if booking2 has higher priority
        """
        if booking1.priority < booking2.priority:
            return -1
        elif booking1.priority > booking2.priority:
            return 1
        return 0
    
    @classmethod
    def get_higher_priority(cls, booking1, booking2):
        """Get the booking with higher priority"""
        if booking1.priority <= booking2.priority:
            return booking1
        return booking2
    
    @classmethod
    def resolve_conflict(cls, existing_booking, new_booking):
        """
        Resolve conflict between two overlapping bookings based on priority
        Academic > Cultural > Practice
        
        Returns:
            dict: Resolution result with winner and message
        """
        if existing_booking.priority < new_booking.priority:
            # Existing booking has higher priority
            return {
                'resolved': False,
                'winner': 'existing',
                'message': f"Existing booking has higher priority: {cls.get_priority_name(existing_booking.priority)}",
                'existing_booking': existing_booking
            }
        elif new_booking.priority < existing_booking.priority:
            # New booking has higher priority
            return {
                'resolved': True,
                'winner': 'new',
                'message': f"New booking has higher priority: {cls.get_priority_name(new_booking.priority)}",
                'should_cancel_existing': True,
                'existing_booking': existing_booking
            }
        else:
            # Equal priority - first come first serve
            if new_booking.created_at < existing_booking.created_at:
                return {
                    'resolved': False,
                    'winner': 'new',
                    'message': "Same priority - first come first serve (new booking created earlier)",
                    'existing_booking': existing_booking
                }
            else:
                return {
                    'resolved': False,
                    'winner': 'existing',
                    'message': "Same priority - first come first serve (existing booking created earlier)",
                    'existing_booking': existing_booking
                }
    
    @classmethod
    def find_conflicting_bookings(cls, venue_id, start_time, end_time, exclude_booking_id=None):
        """Find all bookings that conflict with a time slot"""
        query = VenueBooking.query.filter(
            VenueBooking.venue_id == venue_id,
            VenueBooking.status.in_(['approved', 'confirmed', 'pending_faculty', 'pending_admin', 'pending_security']),
            VenueBooking.start_time < end_time,
            VenueBooking.end_time > start_time
        )
        
        if exclude_booking_id:
            query = query.filter(VenueBooking.id != exclude_booking_id)
        
        return query.order_by(VenueBooking.priority).all()
    
    @classmethod
    def get_highest_priority_booking(cls, venue_id, start_time, end_time):
        """Get the highest priority booking in a time slot"""
        conflicting = cls.find_conflicting_bookings(venue_id, start_time, end_time)
        if not conflicting:
            return None
        conflicting.sort(key=lambda b: b.priority)
        return conflicting[0]
    
    @classmethod
    def can_override_booking(cls, user, target_booking):
        """
        Check if a user can override a booking based on priority and role
        Admin can override any booking
        Faculty can override practice bookings
        Security can only override practice bookings
        """
        if user.role == 'admin':
            return True
        if user.role == 'faculty' and target_booking.priority > PriorityLevel.ACADEMIC:
            return True
        if user.role == 'security' and target_booking.priority > PriorityLevel.PRACTICE:
            return True
        return False
    
    @classmethod
    def escalate_priority(cls, booking_id, user_id, reason=None):
        """
        Escalate a booking's priority (e.g., for emergencies)
        Moves priority up by one level (Practice → Cultural → Academic)
        """
        booking = VenueBooking.query.get(booking_id)
        if not booking:
            return {'success': False, 'error': 'Booking not found'}
        
        from app.models import User
        user = User.query.get(user_id)
        
        if user.role not in ['admin', 'faculty']:
            return {'success': False, 'error': 'Insufficient permissions to escalate priority'}
        
        # Determine new priority (move up one level)
        current_priority = booking.priority
        new_priority = current_priority
        
        if current_priority == PriorityLevel.PRACTICE:
            new_priority = PriorityLevel.CULTURAL
        elif current_priority == PriorityLevel.CULTURAL:
            new_priority = PriorityLevel.ACADEMIC
        else:
            return {'success': False, 'error': 'Booking already has highest priority'}
        
        # Record override
        override = VenuePriorityOverride(
            booking_id=booking_id,
            old_priority=current_priority,
            new_priority=new_priority,
            reason=reason,
            overridden_by=user_id
        )
        
        booking.priority = new_priority
        booking.notes = f"Priority escalated from {cls.get_priority_name(current_priority)} to {cls.get_priority_name(new_priority)} by {user.username}. Reason: {reason or 'Not specified'}"
        
        db.session.add(override)
        db.session.commit()
        
        return {
            'success': True,
            'booking_id': booking.id,
            'old_priority': cls.get_priority_name(current_priority),
            'new_priority': cls.get_priority_name(new_priority),
            'message': f"Booking priority escalated to {cls.get_priority_name(new_priority)}"
        }
    
    @classmethod
    def deescalate_priority(cls, booking_id, user_id, reason=None):
        """
        De-escalate a booking's priority (move down one level)
        Academic → Cultural → Practice
        """
        booking = VenueBooking.query.get(booking_id)
        if not booking:
            return {'success': False, 'error': 'Booking not found'}
        
        from app.models import User
        user = User.query.get(user_id)
        
        if user.role != 'admin':
            return {'success': False, 'error': 'Only admin can de-escalate priority'}
        
        current_priority = booking.priority
        new_priority = current_priority
        
        if current_priority == PriorityLevel.ACADEMIC:
            new_priority = PriorityLevel.CULTURAL
        elif current_priority == PriorityLevel.CULTURAL:
            new_priority = PriorityLevel.PRACTICE
        else:
            return {'success': False, 'error': 'Booking already has lowest priority'}
        
        override = VenuePriorityOverride(
            booking_id=booking_id,
            old_priority=current_priority,
            new_priority=new_priority,
            reason=reason,
            overridden_by=user_id
        )
        
        booking.priority = new_priority
        db.session.add(override)
        db.session.commit()
        
        return {
            'success': True,
            'booking_id': booking.id,
            'old_priority': cls.get_priority_name(current_priority),
            'new_priority': cls.get_priority_name(new_priority),
            'message': f"Booking priority de-escalated to {cls.get_priority_name(new_priority)}"
        }
    
    @classmethod
    def auto_escalate_delayed_approvals(cls, hours_threshold=24):
        """
        Automatically escalate priority for bookings that have been waiting too long
        """
        from app.models import VenueApprovalRequest
        
        threshold_time = datetime.utcnow() - timedelta(hours=hours_threshold)
        
        pending_approvals = VenueApprovalRequest.query.filter(
            VenueApprovalRequest.status == 'pending',
            VenueApprovalRequest.request_date < threshold_time
        ).all()
        
        escalated = 0
        for approval in pending_approvals:
            booking = approval.booking
            
            if booking.priority == PriorityLevel.PRACTICE:
                booking.priority = PriorityLevel.CULTURAL
                escalated += 1
                current_app.logger.info(f"Auto-escalated booking {booking.id} due to delayed approval")
        
        if escalated > 0:
            db.session.commit()
        
        return escalated
    
    @classmethod
    def get_priority_statistics(cls, venue_id=None, start_date=None, end_date=None):
        """Get statistics about booking priorities"""
        if not start_date:
            start_date = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0)
        if not end_date:
            end_date = start_date + timedelta(days=30)
        
        query = VenueBooking.query.filter(
            VenueBooking.start_time >= start_date,
            VenueBooking.end_time <= end_date
        )
        
        if venue_id:
            query = query.filter_by(venue_id=venue_id)
        
        bookings = query.all()
        
        stats = {
            'total': len(bookings),
            'by_priority': {
                'admin': 0,
                'academic': 0,
                'cultural': 0,
                'practice': 0
            },
            'by_priority_percentage': {},
            'average_priority': 0
        }
        
        priority_sum = 0
        for booking in bookings:
            if booking.priority == PriorityLevel.ADMIN:
                stats['by_priority']['admin'] += 1
            elif booking.priority == PriorityLevel.ACADEMIC:
                stats['by_priority']['academic'] += 1
            elif booking.priority == PriorityLevel.CULTURAL:
                stats['by_priority']['cultural'] += 1
            else:
                stats['by_priority']['practice'] += 1
            priority_sum += booking.priority
        
        if stats['total'] > 0:
            for key in stats['by_priority']:
                stats['by_priority_percentage'][key] = round(
                    (stats['by_priority'][key] / stats['total']) * 100, 1
                )
            stats['average_priority'] = round(priority_sum / stats['total'], 1)
        
        return stats
    
    @classmethod
    def get_priority_breakdown_by_event_type(cls, venue_id=None):
        """Get priority breakdown by event type"""
        query = VenueBooking.query
        if venue_id:
            query = query.filter_by(venue_id=venue_id)
        
        bookings = query.all()
        
        breakdown = {}
        for booking in bookings:
            event_type = booking.event_type
            if event_type not in breakdown:
                breakdown[event_type] = {
                    'total': 0,
                    'academic': 0,
                    'cultural': 0,
                    'practice': 0,
                    'admin': 0
                }
            
            breakdown[event_type]['total'] += 1
            if booking.priority == PriorityLevel.ADMIN:
                breakdown[event_type]['admin'] += 1
            elif booking.priority == PriorityLevel.ACADEMIC:
                breakdown[event_type]['academic'] += 1
            elif booking.priority == PriorityLevel.CULTURAL:
                breakdown[event_type]['cultural'] += 1
            else:
                breakdown[event_type]['practice'] += 1
        
        return breakdown
    
    @classmethod
    def get_priority_color_css(cls, priority_value):
        """Get CSS classes for priority styling"""
        try:
            priority = PriorityLevel(priority_value)
            colors = cls.PRIORITY_COLORS
            return {
                'background': f'rgba({cls._hex_to_rgb(colors[priority])}, 0.2)',
                'border': f'1px solid {colors[priority]}',
                'color': colors[priority],
                'icon': cls.PRIORITY_ICONS.get(priority, 'fa-flag'),
                'name': cls.PRIORITY_NAMES.get(priority, 'Standard Priority')
            }
        except ValueError:
            return {
                'background': 'rgba(153, 170, 255, 0.2)',
                'border': '1px solid #99aaff',
                'color': '#99aaff',
                'icon': 'fa-flag',
                'name': 'Standard Priority'
            }
    
    @classmethod
    def _hex_to_rgb(cls, hex_color):
        """Convert hex color to RGB tuple"""
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))