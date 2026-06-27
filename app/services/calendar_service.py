"""
Calendar Service - Calendar Operations and Scheduling
Handles calendar views, event management, and external calendar integration
"""

from datetime import datetime, timedelta, date, time
from flask import current_app, url_for
from icalendar import Calendar as ICalCalendar, Event as ICalEvent
import pytz
import uuid
from app import db
from app.models import VenueBooking, BookingStatus
from app.models import Venue, VenueStatus
from app.models import VenueCalendarEvent, VenueCalendarSettings
from app.services.booking_service import BookingService

class CalendarService:
    """
    Service class for managing calendar operations
    Handles calendar views, event generation, and external calendar integration
    """
    
    # Color mapping for different event types
    EVENT_COLORS = {
        'academic': '#2b6eff',
        'cultural': '#9b4dff',
        'practice': '#00ff88',
        'workshop': '#ffaa33',
        'seminar': '#33ccff',
        'competition': '#ff3366',
        'maintenance': '#ffaa33',
        'blocked': '#ff6666'
    }
    
    # Day names for display
    DAY_NAMES = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    
    @classmethod
    def generate_month_calendar(cls, year, month, events_by_date=None):
        """
        Generate calendar grid for month view
        
        Args:
            year: Year (e.g., 2024)
            month: Month (1-12)
            events_by_date: Dict of events keyed by date string
            
        Returns:
            list: List of weeks, each containing days with event data
        """
        if events_by_date is None:
            events_by_date = {}
        
        # Get first day of month
        first_day = date(year, month, 1)
        start_weekday = first_day.weekday()  # 0 = Monday, 6 = Sunday
        
        # Get last day of month
        if month == 12:
            last_day = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            last_day = date(year, month + 1, 1) - timedelta(days=1)
        
        # Generate all days in calendar grid (including previous/next month)
        calendar_days = []
        
        # Days from previous month
        prev_month = first_day - timedelta(days=start_weekday)
        for i in range(start_weekday):
            day = prev_month + timedelta(days=i)
            date_key = day.strftime('%Y-%m-%d')
            calendar_days.append({
                'date': day,
                'is_current_month': False,
                'is_today': day == date.today(),
                'events': events_by_date.get(date_key, [])
            })
        
        # Days of current month
        for day_num in range(1, last_day.day + 1):
            day = date(year, month, day_num)
            date_key = day.strftime('%Y-%m-%d')
            calendar_days.append({
                'date': day,
                'is_current_month': True,
                'is_today': day == date.today(),
                'events': events_by_date.get(date_key, [])
            })
        
        # Days from next month to complete grid (6 weeks total)
        remaining_days = 42 - len(calendar_days)
        next_month = last_day + timedelta(days=1)
        for i in range(remaining_days):
            day = next_month + timedelta(days=i)
            date_key = day.strftime('%Y-%m-%d')
            calendar_days.append({
                'date': day,
                'is_current_month': False,
                'is_today': day == date.today(),
                'events': events_by_date.get(date_key, [])
            })
        
        # Split into weeks
        weeks = []
        for i in range(0, len(calendar_days), 7):
            weeks.append(calendar_days[i:i+7])
        
        return weeks
    
    @classmethod
    def generate_week_calendar(cls, start_date, events_by_day=None):
        """
        Generate calendar data for week view
        
        Args:
            start_date: Start date of the week
            events_by_day: Dict of events keyed by date string
            
        Returns:
            list: List of days with hourly slots and events
        """
        if events_by_day is None:
            events_by_day = {}
        
        week_days = []
        for i in range(7):
            current_date = start_date + timedelta(days=i)
            date_key = current_date.strftime('%Y-%m-%d')
            
            # Generate hourly slots (8 AM to 10 PM)
            hours = []
            for hour in range(8, 23):
                hour_start = datetime.combine(current_date, time(hour, 0))
                hour_end = datetime.combine(current_date, time(hour + 1, 0))
                
                # Get events for this hour
                hour_events = []
                for event in events_by_day.get(date_key, []):
                    event_start = event.get('start_time')
                    event_end = event.get('end_time')
                    if event_start and event_end:
                        if event_start < hour_end and event_end > hour_start:
                            hour_events.append(event)
                
                hours.append({
                    'hour': hour,
                    'time': f"{hour:02d}:00",
                    'start_time': hour_start,
                    'end_time': hour_end,
                    'events': hour_events
                })
            
            week_days.append({
                'date': current_date,
                'date_key': date_key,
                'day_name': cls.DAY_NAMES[current_date.weekday()],
                'is_today': current_date == date.today(),
                'hours': hours
            })
        
        return week_days
    
    @classmethod
    def generate_day_calendar(cls, target_date, events=None):
        """
        Generate calendar data for day view
        
        Args:
            target_date: Date to display
            events: List of events for the day
            
        Returns:
            dict: Day calendar data with hourly slots
        """
        if events is None:
            events = []
        
        # Generate hourly slots (24 hours)
        hours = []
        for hour in range(0, 24):
            hour_start = datetime.combine(target_date, time(hour, 0))
            hour_end = datetime.combine(target_date, time(hour + 1, 0))
            
            # Get events for this hour
            hour_events = []
            for event in events:
                event_start = event.get('start_time')
                event_end = event.get('end_time')
                if event_start and event_end:
                    if event_start < hour_end and event_end > hour_start:
                        hour_events.append(event)
            
            hours.append({
                'hour': hour,
                'time': f"{hour:02d}:00",
                'start_time': hour_start,
                'end_time': hour_end,
                'events': hour_events
            })
        
        return {
            'date': target_date,
            'date_key': target_date.strftime('%Y-%m-%d'),
            'day_name': cls.DAY_NAMES[target_date.weekday()],
            'is_today': target_date == date.today(),
            'hours': hours
        }
    
    @classmethod
    def get_month_events(cls, venue_id, year, month):
        """
        Get all events for a specific month
        
        Args:
            venue_id: Venue ID (None for all venues)
            year: Year
            month: Month
            
        Returns:
            dict: Events keyed by date
        """
        start_date = datetime(year, month, 1)
        if month == 12:
            end_date = datetime(year + 1, 1, 1)
        else:
            end_date = datetime(year, month + 1, 1)
        
        query = VenueBooking.query.filter(
            VenueBooking.status.in_(['approved', 'confirmed']),
            VenueBooking.start_time >= start_date,
            VenueBooking.start_time < end_date
        )
        
        if venue_id:
            query = query.filter_by(venue_id=venue_id)
        
        bookings = query.all()
        
        # Group by date
        events_by_date = {}
        for booking in bookings:
            date_key = booking.start_time.strftime('%Y-%m-%d')
            if date_key not in events_by_date:
                events_by_date[date_key] = []
            
            events_by_date[date_key].append({
                'id': booking.id,
                'title': booking.title,
                'event_type': booking.event_type,
                'start_time': booking.start_time,
                'end_time': booking.end_time,
                'venue_name': booking.venue.name,
                'venue_id': booking.venue_id,
                'color': cls.EVENT_COLORS.get(booking.event_type, '#00ffff'),
                'description': booking.description,
                'status': booking.status.value,
                'priority': booking.priority
            })
        
        return events_by_date
    
    @classmethod
    def get_week_events(cls, venue_id, start_date):
        """
        Get all events for a specific week
        
        Args:
            venue_id: Venue ID (None for all venues)
            start_date: Start date of the week
            
        Returns:
            dict: Events keyed by date
        """
        end_date = start_date + timedelta(days=7)
        
        query = VenueBooking.query.filter(
            VenueBooking.status.in_(['approved', 'confirmed']),
            VenueBooking.start_time >= datetime.combine(start_date, time.min),
            VenueBooking.end_time <= datetime.combine(end_date, time.max)
        )
        
        if venue_id:
            query = query.filter_by(venue_id=venue_id)
        
        bookings = query.all()
        
        # Group by date
        events_by_date = {}
        for booking in bookings:
            date_key = booking.start_time.strftime('%Y-%m-%d')
            if date_key not in events_by_date:
                events_by_date[date_key] = []
            
            events_by_date[date_key].append({
                'id': booking.id,
                'title': booking.title,
                'event_type': booking.event_type,
                'start_time': booking.start_time,
                'end_time': booking.end_time,
                'venue_name': booking.venue.name,
                'venue_id': booking.venue_id,
                'color': cls.EVENT_COLORS.get(booking.event_type, '#00ffff')
            })
        
        return events_by_date
    
    @classmethod
    def get_day_events(cls, venue_id, target_date):
        """
        Get all events for a specific day
        
        Args:
            venue_id: Venue ID (None for all venues)
            target_date: Target date
            
        Returns:
            list: List of events for the day
        """
        start_time = datetime.combine(target_date, time.min)
        end_time = datetime.combine(target_date, time.max)
        
        query = VenueBooking.query.filter(
            VenueBooking.status.in_(['approved', 'confirmed']),
            VenueBooking.start_time >= start_time,
            VenueBooking.end_time <= end_time
        )
        
        if venue_id:
            query = query.filter_by(venue_id=venue_id)
        
        bookings = query.order_by(VenueBooking.start_time).all()
        
        events = []
        for booking in bookings:
            events.append({
                'id': booking.id,
                'title': booking.title,
                'event_type': booking.event_type,
                'start_time': booking.start_time,
                'end_time': booking.end_time,
                'duration': (booking.end_time - booking.start_time).total_seconds() / 3600,
                'venue_name': booking.venue.name,
                'venue_id': booking.venue_id,
                'venue_capacity': booking.venue.capacity,
                'expected_attendees': booking.expected_attendees,
                'description': booking.description,
                'status': booking.status.value,
                'color': cls.EVENT_COLORS.get(booking.event_type, '#00ffff'),
                'priority': booking.priority
            })
        
        return events
    
    @classmethod
    def get_available_time_slots(cls, venue_id, target_date, duration_minutes=60):
        """
        Get available time slots for a venue on a specific date
        
        Args:
            venue_id: Venue ID
            target_date: Target date
            duration_minutes: Duration of each slot in minutes
            
        Returns:
            list: List of available time slots
        """
        venue = Venue.query.get(venue_id)
        if not venue:
            return []
        
        # Get operating hours
        opens_at = venue.opens_at if venue.opens_at else time(8, 0)
        closes_at = venue.closes_at if venue.closes_at else time(22, 0)
        
        # Get existing bookings for the day
        start_time = datetime.combine(target_date, opens_at)
        end_time = datetime.combine(target_date, closes_at)
        
        bookings = VenueBooking.query.filter(
            VenueBooking.venue_id == venue_id,
            VenueBooking.status.in_(['approved', 'confirmed']),
            VenueBooking.start_time >= start_time,
            VenueBooking.end_time <= end_time
        ).all()
        
        # Generate time slots
        slots = []
        current = start_time
        slot_duration = timedelta(minutes=duration_minutes)
        
        while current + slot_duration <= end_time:
            slot_end = current + slot_duration
            
            # Check if slot is available
            available = True
            for booking in bookings:
                if not (booking.end_time <= current or booking.start_time >= slot_end):
                    available = False
                    break
            
            slots.append({
                'start_time': current,
                'end_time': slot_end,
                'start': current.strftime('%H:%M'),
                'end': slot_end.strftime('%H:%M'),
                'available': available,
                'duration_minutes': duration_minutes
            })
            
            current += slot_duration
        
        return slots
    
    @classmethod
    def get_venue_calendar_heatmap(cls, venue_id, start_date, end_date):
        """
        Generate heatmap data for venue usage
        
        Args:
            venue_id: Venue ID
            start_date: Start date
            end_date: End date
            
        Returns:
            dict: Heatmap data with usage intensity by day and hour
        """
        venue = Venue.query.get(venue_id)
        if not venue:
            return {}
        
        # Get all bookings in date range
        bookings = VenueBooking.query.filter(
            VenueBooking.venue_id == venue_id,
            VenueBooking.status.in_(['approved', 'confirmed']),
            VenueBooking.start_time >= datetime.combine(start_date, time.min),
            VenueBooking.end_time <= datetime.combine(end_date, time.max)
        ).all()
        
        # Create heatmap grid
        heatmap = {}
        current_date = start_date
        while current_date <= end_date:
            date_key = current_date.strftime('%Y-%m-%d')
            heatmap[date_key] = {hour: 0 for hour in range(0, 24)}
            
            # Count bookings for each hour
            for booking in bookings:
                if booking.start_time.date() == current_date:
                    hour = booking.start_time.hour
                    heatmap[date_key][hour] += 1
            
            current_date += timedelta(days=1)
        
        return heatmap
    
    @classmethod
    def export_to_ical(cls, bookings, user_name=None):
        """
        Export bookings to iCal format
        
        Args:
            bookings: List of booking objects
            user_name: Name for the calendar
            
        Returns:
            bytes: iCal formatted data
        """
        cal = ICalCalendar()
        cal.add('prodid', '-//EventX//Venue Calendar//EN')
        cal.add('version', '2.0')
        cal.add('calscale', 'GREGORIAN')
        cal.add('method', 'PUBLISH')
        
        if user_name:
            cal.add('x-wr-calname', f"EventX - {user_name}'s Calendar")
            cal.add('x-wr-caldesc', 'EventX Venue Bookings Calendar')
        
        for booking in bookings:
            event = ICalEvent()
            event.add('summary', booking.title)
            event.add('dtstart', booking.start_time)
            event.add('dtend', booking.end_time)
            event.add('dtstamp', booking.created_at)
            event.add('location', booking.venue.name)
            event.add('description', booking.description or 'No description provided')
            event.add('uid', f"{booking.id}@eventx.com")
            event.add('status', 'CONFIRMED' if booking.status == BookingStatus.CONFIRMED else 'TENTATIVE')
            
            cal.add_component(event)
        
        return cal.to_ical()
    
    @classmethod
    def generate_google_calendar_url(cls, booking):
        """
        Generate Google Calendar URL for a booking
        
        Args:
            booking: VenueBooking object
            
        Returns:
            str: Google Calendar URL
        """
        start_time = booking.start_time.strftime('%Y%m%dT%H%M%SZ')
        end_time = booking.end_time.strftime('%Y%m%dT%H%M%SZ')
        
        params = {
            'action': 'TEMPLATE',
            'text': booking.title,
            'dates': f"{start_time}/{end_time}",
            'details': booking.description or 'EventX Booking',
            'location': booking.venue.name,
            'sf': 'true',
            'output': 'xml'
        }
        
        url = 'https://www.google.com/calendar/render?' + '&'.join([f"{k}={v}" for k, v in params.items()])
        return url
    
    @classmethod
    def generate_outlook_calendar_url(cls, booking):
        """
        Generate Outlook Calendar URL for a booking
        
        Args:
            booking: VenueBooking object
            
        Returns:
            str: Outlook Calendar URL
        """
        start_time = booking.start_time.strftime('%Y-%m-%dT%H:%M:%S')
        end_time = booking.end_time.strftime('%Y-%m-%dT%H:%M:%S')
        
        params = {
            'path': '/calendar/action/compose',
            'rru': 'addevent',
            'startdt': start_time,
            'enddt': end_time,
            'subject': booking.title,
            'body': booking.description or 'EventX Booking',
            'location': booking.venue.name
        }
        
        url = 'https://outlook.live.com/calendar/0/deeplink/compose?' + '&'.join([f"{k}={v}" for k, v in params.items()])
        return url
    
    @classmethod
    def generate_apple_calendar_file(cls, booking):
        """
        Generate Apple Calendar (.ics) file for a booking
        
        Args:
            booking: VenueBooking object
            
        Returns:
            bytes: iCal formatted data for single event
        """
        cal = ICalCalendar()
        cal.add('prodid', '-//EventX//Venue Calendar//EN')
        cal.add('version', '2.0')
        
        event = ICalEvent()
        event.add('summary', booking.title)
        event.add('dtstart', booking.start_time)
        event.add('dtend', booking.end_time)
        event.add('dtstamp', datetime.utcnow())
        event.add('location', booking.venue.name)
        event.add('description', booking.description or 'No description provided')
        event.add('uid', f"{booking.id}@eventx.com")
        
        cal.add_component(event)
        
        return cal.to_ical()
    
    @classmethod
    def get_calendar_feed_token(cls, user_id):
        """
        Generate a unique token for calendar feed subscription
        
        Args:
            user_id: User ID
            
        Returns:
            str: Unique token
        """
        token = str(uuid.uuid4()).replace('-', '')[:32]
        
        # Store token in app config
        feed_data = {
            'user_id': user_id,
            'token': token,
            'created_at': datetime.utcnow(),
            'expires_at': datetime.utcnow() + timedelta(days=365)
        }
        
        current_app.config.setdefault('calendar_feeds', {})
        current_app.config['calendar_feeds'][token] = feed_data
        
        return token
    
    @classmethod
    def get_calendar_feed_url(cls, token):
        """
        Get calendar feed URL for a token
        
        Args:
            token: Feed token
            
        Returns:
            str: Full URL for calendar feed
        """
        return url_for('calendar.calendar_feed', token=token, _external=True)
    
    @classmethod
    def validate_feed_token(cls, token):
        """
        Validate a calendar feed token
        
        Args:
            token: Feed token
            
        Returns:
            dict: Token data if valid, None otherwise
        """
        feeds = current_app.config.get('calendar_feeds', {})
        feed_data = feeds.get(token)
        
        if not feed_data:
            return None
        
        # Check expiration
        expires_at = feed_data.get('expires_at')
        if expires_at and expires_at < datetime.utcnow():
            return None
        
        return feed_data
    
    @classmethod
    def get_booking_slots_for_date(cls, venue_id, target_date):
        """
        Get all booking slots for a specific date
        
        Args:
            venue_id: Venue ID
            target_date: Target date
            
        Returns:
            list: List of booking slots with time and status
        """
        venue = Venue.query.get(venue_id)
        if not venue:
            return []
        
        start_time = datetime.combine(target_date, venue.opens_at if venue.opens_at else time(0, 0))
        end_time = datetime.combine(target_date, venue.closes_at if venue.closes_at else time(23, 59))
        
        bookings = VenueBooking.query.filter(
            VenueBooking.venue_id == venue_id,
            VenueBooking.status.in_(['approved', 'confirmed']),
            VenueBooking.start_time >= start_time,
            VenueBooking.end_time <= end_time
        ).order_by(VenueBooking.start_time).all()
        
        slots = []
        for booking in bookings:
            slots.append({
                'id': booking.id,
                'title': booking.title,
                'start': booking.start_time.strftime('%H:%M'),
                'end': booking.end_time.strftime('%H:%M'),
                'start_time': booking.start_time,
                'end_time': booking.end_time,
                'event_type': booking.event_type,
                'status': booking.status.value,
                'venue_name': booking.venue.name
            })
        
        return slots
    
    @classmethod
    def get_user_calendar_settings(cls, user_id):
        """
        Get calendar settings for a user
        
        Args:
            user_id: User ID
            
        Returns:
            VenueCalendarSettings: User's calendar settings
        """
        settings = VenueCalendarSettings.query.filter_by(user_id=user_id).first()
        if not settings:
            # Create default settings
            settings = VenueCalendarSettings(
                user_id=user_id,
                default_view='month',
                show_weekends=True,
                working_hours_start=time(8, 0),
                working_hours_end=time(20, 0)
            )
            db.session.add(settings)
            db.session.commit()
        
        return settings
    
    @classmethod
    def update_user_calendar_settings(cls, user_id, data):
        """
        Update calendar settings for a user
        
        Args:
            user_id: User ID
            data: Dictionary with updated settings
            
        Returns:
            VenueCalendarSettings: Updated settings
        """
        settings = cls.get_user_calendar_settings(user_id)
        
        if 'default_view' in data:
            settings.default_view = data['default_view']
        if 'show_weekends' in data:
            settings.show_weekends = data['show_weekends']
        if 'working_hours_start' in data:
            settings.working_hours_start = cls._parse_time(data['working_hours_start'])
        if 'working_hours_end' in data:
            settings.working_hours_end = cls._parse_time(data['working_hours_end'])
        
        settings.updated_at = datetime.utcnow()
        db.session.commit()
        
        return settings
    
    @classmethod
    def _parse_time(cls, time_str):
        """Parse time string to time object"""
        if not time_str:
            return None
        try:
            return datetime.strptime(time_str, '%H:%M').time()
        except ValueError:
            return None