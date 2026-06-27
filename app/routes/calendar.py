"""
Calendar Routes - Venue Calendar Management
Handles calendar views, event scheduling, and external calendar integration
"""

import json
import uuid
from datetime import datetime, timedelta, date, time
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, abort, current_app, send_file
from flask_login import login_required, current_user
from icalendar import Calendar as ICalCalendar, Event as ICalEvent
import io
import pytz

from app import db
from app.models import Venue, VenueStatus, VenueBooking, BookingStatus, VenueCalendarSettings
from app.services.calendar_service import CalendarService
from app.services.venue_service import VenueService
from app.services.booking_service import BookingService

# Create blueprint
calendar_bp = Blueprint('calendar', __name__, url_prefix='/calendar')


# ============================================
# Calendar Views
# ============================================

@calendar_bp.route('/')
@login_required
def index():
    """Main calendar view"""
    venues = Venue.query.filter_by(status=VenueStatus.ACTIVE).all()
    user_settings = CalendarService.get_user_calendar_settings(current_user.id)
    return render_template('calendar/index.html', 
                          venues=venues, 
                          settings=user_settings)


@calendar_bp.route('/month')
@login_required
def month_view():
    """Month view calendar"""
    year = request.args.get('year', type=int)
    month = request.args.get('month', type=int)
    venue_id = request.args.get('venue_id', type=int)
    
    if not year or not month:
        now = datetime.utcnow()
        year = now.year
        month = now.month
    
    # Get events for the month
    events_by_date = CalendarService.get_month_events(venue_id, year, month)
    
    # Generate calendar grid
    calendar_grid = CalendarService.generate_month_calendar(year, month, events_by_date)
    
    return render_template('calendar/month.html', 
                          calendar_grid=calendar_grid,
                          year=year, 
                          month=month,
                          venue_id=venue_id,
                          venues=Venue.query.filter_by(status=VenueStatus.ACTIVE).all())


@calendar_bp.route('/week')
@login_required
def week_view():
    """Week view calendar"""
    date_str = request.args.get('date')
    venue_id = request.args.get('venue_id', type=int)
    
    if date_str:
        current_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    else:
        current_date = datetime.utcnow().date()
    
    # Get start of week (Monday)
    start_of_week = current_date - timedelta(days=current_date.weekday())
    
    # Get events for the week
    events_by_day = CalendarService.get_week_events(venue_id, start_of_week)
    
    # Generate week calendar
    week_days = CalendarService.generate_week_calendar(start_of_week, events_by_day)
    
    return render_template('calendar/week.html',
                          week_days=week_days,
                          current_date=current_date,
                          start_of_week=start_of_week,
                          venue_id=venue_id,
                          venues=Venue.query.filter_by(status=VenueStatus.ACTIVE).all())


@calendar_bp.route('/day')
@login_required
def day_view():
    """Day view calendar"""
    date_str = request.args.get('date')
    venue_id = request.args.get('venue_id', type=int)
    
    if date_str:
        current_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    else:
        current_date = datetime.utcnow().date()
    
    # Get events for the day
    events = CalendarService.get_day_events(venue_id, current_date)
    
    # Generate day calendar
    day_calendar = CalendarService.generate_day_calendar(current_date, events)
    
    return render_template('calendar/day.html',
                          day_calendar=day_calendar,
                          venue_id=venue_id,
                          venues=Venue.query.filter_by(status=VenueStatus.ACTIVE).all())


@calendar_bp.route('/venue/<int:venue_id>')
@login_required
def venue_calendar(venue_id):
    """Calendar view for a specific venue"""
    venue = Venue.query.get_or_404(venue_id)
    user_settings = CalendarService.get_user_calendar_settings(current_user.id)
    return render_template('calendar/venue.html', 
                          venue=venue, 
                          settings=user_settings)


# ============================================
# Calendar Settings
# ============================================

@calendar_bp.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    """User calendar settings"""
    if request.method == 'POST':
        try:
            data = {
                'default_view': request.form.get('default_view'),
                'show_weekends': request.form.get('show_weekends') == 'on',
                'working_hours_start': request.form.get('working_hours_start'),
                'working_hours_end': request.form.get('working_hours_end')
            }
            settings = CalendarService.update_user_calendar_settings(current_user.id, data)
            flash('Calendar settings updated successfully', 'success')
            return redirect(url_for('calendar.settings'))
        except Exception as e:
            flash(str(e), 'danger')
    
    settings = CalendarService.get_user_calendar_settings(current_user.id)
    return render_template('calendar/settings.html', settings=settings)


# ============================================
# API Endpoints
# ============================================

@calendar_bp.route('/api/events')
@login_required
def api_events():
    """API endpoint for calendar events (FullCalendar compatible)"""
    start = request.args.get('start')
    end = request.args.get('end')
    venue_id = request.args.get('venue_id', type=int)
    
    if not start or not end:
        return jsonify([])
    
    start_date = datetime.fromisoformat(start.replace('Z', '+00:00'))
    end_date = datetime.fromisoformat(end.replace('Z', '+00:00'))
    
    query = VenueBooking.query.filter(
        VenueBooking.status.in_(['approved', 'confirmed']),
        VenueBooking.start_time < end_date,
        VenueBooking.end_time > start_date
    )
    
    if venue_id:
        query = query.filter_by(venue_id=venue_id)
    
    bookings = query.all()
    
    events = []
    for booking in bookings:
        events.append({
            'id': booking.id,
            'title': booking.title,
            'start': booking.start_time.isoformat(),
            'end': booking.end_time.isoformat(),
            'allDay': False,
            'venue': booking.venue.name,
            'venue_id': booking.venue_id,
            'event_type': booking.event_type,
            'status': booking.status.value,
            'description': booking.description,
            'color': CalendarService.EVENT_COLORS.get(booking.event_type, '#00ffff'),
            'textColor': '#ffffff',
            'extendedProps': {
                'venue_name': booking.venue.name,
                'event_type': booking.event_type,
                'expected_attendees': booking.expected_attendees,
                'priority': booking.priority,
                'priority_name': booking.get_priority_level()
            }
        })
    
    return jsonify(events)


@calendar_bp.route('/api/events/monthly', methods=['POST'])
@login_required
def api_monthly_events():
    """API endpoint for monthly event summary"""
    data = request.get_json()
    year = data.get('year')
    month = data.get('month')
    venue_id = data.get('venue_id')
    
    if not year or not month:
        return jsonify({'error': 'Year and month required'}), 400
    
    events_by_date = CalendarService.get_month_events(venue_id, year, month)
    return jsonify(events_by_date)


@calendar_bp.route('/api/availability/week', methods=['POST'])
@login_required
def api_weekly_availability():
    """API endpoint for weekly availability check"""
    data = request.get_json()
    venue_id = data.get('venue_id')
    week_start = data.get('week_start')
    
    if not venue_id or not week_start:
        return jsonify({'error': 'Venue ID and week start required'}), 400
    
    start_date = datetime.strptime(week_start, '%Y-%m-%d').date()
    end_date = start_date + timedelta(days=6)
    
    # Get all bookings for the week
    bookings = VenueBooking.query.filter(
        VenueBooking.venue_id == venue_id,
        VenueBooking.status.in_(['approved', 'confirmed']),
        VenueBooking.start_time >= datetime.combine(start_date, time.min),
        VenueBooking.end_time <= datetime.combine(end_date, time.max)
    ).all()
    
    # Generate availability grid
    availability = {}
    for i in range(7):
        day_date = start_date + timedelta(days=i)
        day_bookings = [b for b in bookings if b.start_time.date() == day_date]
        
        # Get available slots
        slots = CalendarService.get_available_time_slots(venue_id, day_date)
        
        availability[day_date.isoformat()] = slots
    
    return jsonify({
        'venue_id': venue_id,
        'week_start': week_start,
        'availability': availability
    })


@calendar_bp.route('/api/available-slots')
@login_required
def api_available_slots():
    """API endpoint to get available time slots for a venue on a specific date"""
    venue_id = request.args.get('venue_id', type=int)
    date_str = request.args.get('date')
    duration = request.args.get('duration', 60, type=int)
    
    if not venue_id or not date_str:
        return jsonify({'error': 'Missing required fields'}), 400
    
    target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    slots = CalendarService.get_available_time_slots(venue_id, target_date, duration)
    
    return jsonify({
        'venue_id': venue_id,
        'date': date_str,
        'slots': slots
    })


# ============================================
# External Calendar Integration
# ============================================

@calendar_bp.route('/export/<int:booking_id>')
@login_required
def export_to_ical(booking_id):
    """Export a single booking to iCal format"""
    booking = VenueBooking.query.get_or_404(booking_id)
    
    # Check permissions
    if current_user.role != 'admin' and booking.created_by != current_user.id:
        flash('You do not have permission to export this booking', 'danger')
        return redirect(url_for('calendar.index'))
    
    cal_data = CalendarService.export_to_ical([booking], current_user.username)
    
    return send_file(
        io.BytesIO(cal_data),
        mimetype='text/calendar',
        as_attachment=True,
        download_name=f"{booking.title.replace(' ', '_')}.ics"
    )


@calendar_bp.route('/export/subscribe')
@login_required
def subscribe_calendar():
    """Generate subscription URL for external calendar"""
    token = CalendarService.get_calendar_feed_token(current_user.id)
    subscription_url = CalendarService.get_calendar_feed_url(token)
    
    return render_template('calendar/subscribe.html', 
                          subscription_url=subscription_url,
                          token=token)


@calendar_bp.route('/feed/<token>')
def calendar_feed(token):
    """iCal feed for external calendar subscription"""
    feed_data = CalendarService.validate_feed_token(token)
    
    if not feed_data:
        abort(404, description='Invalid or expired subscription token')
    
    user_id = feed_data['user_id']
    
    # Get user's bookings
    if current_user.is_authenticated and current_user.id == user_id:
        # User is authenticated and matches token
        bookings = VenueBooking.query.filter(
            VenueBooking.created_by == user_id,
            VenueBooking.status.in_(['approved', 'confirmed'])
        ).all()
    else:
        # Public feed - only show approved bookings
        bookings = VenueBooking.query.filter(
            VenueBooking.status.in_(['approved', 'confirmed'])
        ).all()
    
    cal_data = CalendarService.export_to_ical(bookings)
    
    return send_file(
        io.BytesIO(cal_data),
        mimetype='text/calendar',
        as_attachment=False,
        download_name=f"eventx_calendar.ics"
    )


# ============================================
# Google Calendar Integration
# ============================================

@calendar_bp.route('/google/add/<int:booking_id>')
@login_required
def add_to_google_calendar(booking_id):
    """Add booking to Google Calendar"""
    booking = VenueBooking.query.get_or_404(booking_id)
    
    # Check permissions
    if current_user.role != 'admin' and booking.created_by != current_user.id:
        flash('You do not have permission to add this booking to your calendar', 'danger')
        return redirect(url_for('calendar.index'))
    
    url = CalendarService.generate_google_calendar_url(booking)
    return redirect(url)


@calendar_bp.route('/outlook/add/<int:booking_id>')
@login_required
def add_to_outlook_calendar(booking_id):
    """Add booking to Outlook Calendar"""
    booking = VenueBooking.query.get_or_404(booking_id)
    
    # Check permissions
    if current_user.role != 'admin' and booking.created_by != current_user.id:
        flash('You do not have permission to add this booking to your calendar', 'danger')
        return redirect(url_for('calendar.index'))
    
    url = CalendarService.generate_outlook_calendar_url(booking)
    return redirect(url)


@calendar_bp.route('/apple/download/<int:booking_id>')
@login_required
def download_apple_calendar(booking_id):
    """Download Apple Calendar (.ics) file for a booking"""
    booking = VenueBooking.query.get_or_404(booking_id)
    
    # Check permissions
    if current_user.role != 'admin' and booking.created_by != current_user.id:
        flash('You do not have permission to download this booking', 'danger')
        return redirect(url_for('calendar.index'))
    
    cal_data = CalendarService.generate_apple_calendar_file(booking)
    
    return send_file(
        io.BytesIO(cal_data),
        mimetype='text/calendar',
        as_attachment=True,
        download_name=f"{booking.title.replace(' ', '_')}.ics"
    )


# ============================================
# Calendar Heatmap
# ============================================

@calendar_bp.route('/heatmap')
@login_required
def heatmap():
    """Venue usage heatmap view"""
    if current_user.role != 'admin':
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('calendar.index'))
    
    venue_id = request.args.get('venue_id', type=int)
    year = request.args.get('year', type=int, default=datetime.utcnow().year)
    
    venues = Venue.query.filter_by(status=VenueStatus.ACTIVE).all()
    
    return render_template('calendar/heatmap.html',
                          venues=venues,
                          selected_venue=venue_id,
                          year=year)


@calendar_bp.route('/api/heatmap')
@login_required
def api_heatmap_data():
    """API endpoint for heatmap data"""
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    venue_id = request.args.get('venue_id', type=int)
    year = request.args.get('year', type=int, default=datetime.utcnow().year)
    month = request.args.get('month', type=int)
    
    if not venue_id:
        return jsonify({'error': 'Venue ID required'}), 400
    
    if month:
        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = date(year, month + 1, 1) - timedelta(days=1)
    else:
        start_date = date(year, 1, 1)
        end_date = date(year, 12, 31)
    
    heatmap_data = CalendarService.get_venue_calendar_heatmap(venue_id, start_date, end_date)
    
    return jsonify({
        'venue_id': venue_id,
        'year': year,
        'month': month,
        'heatmap': heatmap_data
    })