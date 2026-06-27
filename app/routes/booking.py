"""
Booking Routes - Venue Booking Management
Handles booking creation, modification, cancellation, and approval workflow
"""

from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, abort, current_app
from flask_login import login_required, current_user
from sqlalchemy import func, and_, or_

from app import db
from app.models import Venue, VenueStatus, VenueBooking, BookingStatus, BookingPriority, VenueBookingHistory, VenueApprovalRequest, User
from app.services.booking_service import BookingService
from app.services.venue_service import VenueService
from app.services.priority_service import PriorityService
from app.services.approval_service import ApprovalService
from app.services.notification_service import NotificationService

# Create blueprint
booking_bp = Blueprint('booking', __name__, url_prefix='/bookings')


# ============================================
# Booking Views
# ============================================

@booking_bp.route('/')
@login_required
def index():
    """List all bookings for the current user"""
    if current_user.role == 'admin':
        bookings = VenueBooking.query.order_by(VenueBooking.start_time.desc()).all()
    elif current_user.role in ['faculty', 'security']:
        # Faculty and security can see all bookings
        bookings = VenueBooking.query.order_by(VenueBooking.start_time.desc()).all()
    else:
        # Regular users see their own bookings
        bookings = VenueBooking.query.filter_by(created_by=current_user.id).order_by(VenueBooking.start_time.desc()).all()
    
    return render_template('booking/index.html', bookings=bookings)


@booking_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    """Create a new booking"""
    if request.method == 'POST':
        try:
            data = {
                'title': request.form.get('title'),
                'description': request.form.get('description'),
                'event_type': request.form.get('event_type', 'practice'),
                'venue_id': request.form.get('venue_id', type=int),
                'start_time': datetime.strptime(
                    f"{request.form.get('date')} {request.form.get('start_time')}", 
                    '%Y-%m-%d %H:%M'
                ),
                'end_time': datetime.strptime(
                    f"{request.form.get('date')} {request.form.get('end_time')}", 
                    '%Y-%m-%d %H:%M'
                ),
                'setup_time': request.form.get('setup_time', 30, type=int),
                'cleanup_time': request.form.get('cleanup_time', 30, type=int),
                'expected_attendees': request.form.get('expected_attendees', 0, type=int),
                'requirements': request.form.get('requirements', {}),
                'special_requests': request.form.get('special_requests', '')
            }
            
            # Validate inputs
            if not data['title']:
                flash('Please enter a booking title', 'warning')
                return redirect(url_for('booking.create'))
            
            if not data['venue_id']:
                flash('Please select a venue', 'warning')
                return redirect(url_for('booking.create'))
            
            if data['start_time'] >= data['end_time']:
                flash('End time must be after start time', 'warning')
                return redirect(url_for('booking.create'))
            
            if data['start_time'] < datetime.utcnow():
                flash('Cannot book for past dates', 'warning')
                return redirect(url_for('booking.create'))
            
            # Create booking using service
            booking = BookingService.create_booking(data, current_user.id)
            
            flash(f'Booking "{booking.title}" created successfully! Waiting for approval.', 'success')
            
            # Send confirmation email
            NotificationService.send_booking_confirmation(booking.id)
            
            return redirect(url_for('booking.view', booking_id=booking.id))
            
        except ValueError as e:
            flash(str(e), 'danger')
        except Exception as e:
            current_app.logger.error(f"Booking creation error: {e}")
            flash('An error occurred while creating the booking', 'danger')
    
    # GET request - show form
    venues = Venue.query.filter_by(status=VenueStatus.ACTIVE).all()
    return render_template('booking/create.html', venues=venues)


@booking_bp.route('/<int:booking_id>')
@login_required
def view(booking_id):
    """View booking details"""
    booking = VenueBooking.query.get_or_404(booking_id)
    
    # Check permissions
    if current_user.role not in ['admin', 'faculty', 'security'] and booking.created_by != current_user.id:
        flash('You do not have permission to view this booking', 'danger')
        return redirect(url_for('booking.index'))
    
    # Get approval requests
    approvals = VenueApprovalRequest.query.filter_by(booking_id=booking_id).all()
    
    # Get history
    history = VenueBookingHistory.query.filter_by(booking_id=booking_id).order_by(VenueBookingHistory.performed_at.desc()).all()
    
    return render_template('booking/view.html', 
                          booking=booking, 
                          approvals=approvals,
                          history=history)


@booking_bp.route('/<int:booking_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(booking_id):
    """Edit an existing booking"""
    booking = VenueBooking.query.get_or_404(booking_id)
    
    # Check permissions - only creator or admin can edit
    if current_user.role != 'admin' and booking.created_by != current_user.id:
        flash('You do not have permission to edit this booking', 'danger')
        return redirect(url_for('booking.index'))
    
    # Check if booking can be edited
    if booking.status not in [BookingStatus.DRAFT, BookingStatus.PENDING_FACULTY]:
        flash('This booking cannot be edited as it has already been processed', 'warning')
        return redirect(url_for('booking.view', booking_id=booking.id))
    
    if request.method == 'POST':
        try:
            data = {
                'title': request.form.get('title'),
                'description': request.form.get('description'),
                'event_type': request.form.get('event_type'),
                'venue_id': request.form.get('venue_id', type=int),
                'start_time': datetime.strptime(
                    f"{request.form.get('date')} {request.form.get('start_time')}", 
                    '%Y-%m-%d %H:%M'
                ),
                'end_time': datetime.strptime(
                    f"{request.form.get('date')} {request.form.get('end_time')}", 
                    '%Y-%m-%d %H:%M'
                ),
                'setup_time': request.form.get('setup_time', 30, type=int),
                'cleanup_time': request.form.get('cleanup_time', 30, type=int),
                'expected_attendees': request.form.get('expected_attendees', 0, type=int),
                'requirements': request.form.get('requirements', {}),
                'special_requests': request.form.get('special_requests', '')
            }
            
            booking = BookingService.update_booking(booking_id, data, current_user.id)
            flash('Booking updated successfully', 'success')
            return redirect(url_for('booking.view', booking_id=booking.id))
            
        except Exception as e:
            flash(str(e), 'danger')
    
    venues = Venue.query.filter_by(status=VenueStatus.ACTIVE).all()
    return render_template('booking/edit.html', booking=booking, venues=venues)


@booking_bp.route('/<int:booking_id>/cancel', methods=['POST'])
@login_required
def cancel(booking_id):
    """Cancel a booking"""
    booking = VenueBooking.query.get_or_404(booking_id)
    
    # Check permissions
    if current_user.role not in ['admin', 'security'] and booking.created_by != current_user.id:
        flash('You do not have permission to cancel this booking', 'danger')
        return redirect(url_for('booking.index'))
    
    reason = request.form.get('reason', 'No reason provided')
    
    try:
        BookingService.cancel_booking(booking_id, current_user.id, reason)
        NotificationService.send_booking_cancellation(booking_id, reason)
        flash('Booking cancelled successfully', 'success')
    except Exception as e:
        flash(str(e), 'danger')
    
    return redirect(url_for('booking.index'))


# ============================================
# Booking Check-in/out (Security)
# ============================================

@booking_bp.route('/<int:booking_id>/check-in', methods=['POST'])
@login_required
def check_in(booking_id):
    """Check in for a booking (security only)"""
    if current_user.role not in ['security', 'admin']:
        flash('Only security personnel can check in bookings', 'danger')
        return redirect(url_for('booking.index'))
    
    booking = VenueBooking.query.get_or_404(booking_id)
    
    if booking.status != BookingStatus.CONFIRMED:
        flash('Booking must be confirmed before check-in', 'warning')
        return redirect(url_for('booking.view', booking_id=booking.id))
    
    booking.checked_in_at = datetime.utcnow()
    booking.security_check_in_by = current_user.id
    
    # Log history
    history = VenueBookingHistory(
        booking_id=booking_id,
        action='checked_in',
        old_status=booking.status.value,
        new_status=booking.status.value,
        performed_by=current_user.id
    )
    db.session.add(history)
    db.session.commit()
    
    flash('Check-in successful', 'success')
    return redirect(url_for('booking.view', booking_id=booking.id))


@booking_bp.route('/<int:booking_id>/check-out', methods=['POST'])
@login_required
def check_out(booking_id):
    """Check out from a booking (security only)"""
    if current_user.role not in ['security', 'admin']:
        flash('Only security personnel can check out bookings', 'danger')
        return redirect(url_for('booking.index'))
    
    booking = VenueBooking.query.get_or_404(booking_id)
    
    if not booking.checked_in_at:
        flash('Booking must be checked in first', 'warning')
        return redirect(url_for('booking.view', booking_id=booking.id))
    
    booking.checked_out_at = datetime.utcnow()
    
    # Log history
    history = VenueBookingHistory(
        booking_id=booking_id,
        action='checked_out',
        old_status=booking.status.value,
        new_status=booking.status.value,
        performed_by=current_user.id
    )
    db.session.add(history)
    db.session.commit()
    
    flash('Check-out successful', 'success')
    return redirect(url_for('booking.view', booking_id=booking.id))


# ============================================
# My Bookings
# ============================================

@booking_bp.route('/my')
@login_required
def my_bookings():
    """View current user's bookings"""
    bookings = VenueBooking.query.filter_by(created_by=current_user.id).order_by(VenueBooking.start_time.desc()).all()
    
    upcoming = [b for b in bookings if b.start_time >= datetime.utcnow() and b.status not in [BookingStatus.CANCELLED, BookingStatus.REJECTED]]
    past = [b for b in bookings if b.start_time < datetime.utcnow() or b.status in [BookingStatus.CANCELLED, BookingStatus.REJECTED]]
    
    return render_template('booking/my_bookings.html', 
                          upcoming=upcoming, 
                          past=past)


# ============================================
# API Endpoints
# ============================================

@booking_bp.route('/api/bookings', methods=['GET'])
@login_required
def api_get_bookings():
    """API endpoint to get bookings"""
    status = request.args.get('status')
    venue_id = request.args.get('venue_id', type=int)
    event_type = request.args.get('event_type')
    
    query = VenueBooking.query
    
    if current_user.role not in ['admin', 'faculty', 'security']:
        query = query.filter_by(created_by=current_user.id)
    
    if status:
        query = query.filter_by(status=status)
    if venue_id:
        query = query.filter_by(venue_id=venue_id)
    if event_type:
        query = query.filter_by(event_type=event_type)
    
    bookings = query.order_by(VenueBooking.start_time.desc()).all()
    
    return jsonify([{
        'id': b.id,
        'title': b.title,
        'event_type': b.event_type,
        'venue_name': b.venue.name,
        'start_time': b.start_time.isoformat(),
        'end_time': b.end_time.isoformat(),
        'status': b.status.value,
        'priority': b.priority,
        'expected_attendees': b.expected_attendees
    } for b in bookings])


@booking_bp.route('/api/bookings/<int:booking_id>', methods=['GET'])
@login_required
def api_get_booking(booking_id):
    """API endpoint to get a single booking"""
    booking = VenueBooking.query.get_or_404(booking_id)
    
    # Check permissions
    if current_user.role not in ['admin', 'faculty', 'security'] and booking.created_by != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    approvals = VenueApprovalRequest.query.filter_by(booking_id=booking_id).all()
    
    return jsonify({
        'id': booking.id,
        'title': booking.title,
        'description': booking.description,
        'event_type': booking.event_type,
        'venue': {
            'id': booking.venue.id,
            'name': booking.venue.name,
            'type': booking.venue.type.value,
            'capacity': booking.venue.capacity
        },
        'start_time': booking.start_time.isoformat(),
        'end_time': booking.end_time.isoformat(),
        'setup_time': booking.setup_time,
        'cleanup_time': booking.cleanup_time,
        'expected_attendees': booking.expected_attendees,
        'priority': booking.priority,
        'priority_name': booking.get_priority_level(),
        'status': booking.status.value,
        'requirements': booking.requirements,
        'special_requests': booking.special_requests,
        'created_by': booking.created_by_username if hasattr(booking, 'created_by_username') else None,
        'created_at': booking.created_at.isoformat(),
        'approvals': [{
            'stage': a.stage,
            'status': a.status,
            'comments': a.comments,
            'response_date': a.response_date.isoformat() if a.response_date else None
        } for a in approvals]
    })


@booking_bp.route('/api/bookings/<int:booking_id>/status', methods=['PUT'])
@login_required
def api_update_booking_status(booking_id):
    """API endpoint to update booking status"""
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    booking = VenueBooking.query.get_or_404(booking_id)
    data = request.get_json()
    new_status = data.get('status')
    
    if new_status not in [s.value for s in BookingStatus]:
        return jsonify({'error': 'Invalid status'}), 400
    
    booking.status = BookingStatus(new_status)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'booking_id': booking.id,
        'status': booking.status.value
    })


@booking_bp.route('/api/bookings/check-availability', methods=['POST'])
def api_check_availability():
    """API endpoint to check venue availability"""
    data = request.get_json()
    
    venue_id = data.get('venue_id')
    start_time = datetime.fromisoformat(data.get('start_time'))
    end_time = datetime.fromisoformat(data.get('end_time'))
    exclude_booking_id = data.get('exclude_booking_id')
    
    if not venue_id or not start_time or not end_time:
        return jsonify({'error': 'Missing required fields'}), 400
    
    venue = Venue.query.get(venue_id)
    if not venue:
        return jsonify({'error': 'Venue not found'}), 404
    
    available = venue.is_available(start_time, end_time, exclude_booking_id)
    
    # Get alternative venues if not available
    alternatives = []
    if not available:
        alternatives = VenueService.get_alternative_venues(venue_id, start_time, end_time)
    
    return jsonify({
        'available': available,
        'venue_id': venue.id,
        'venue_name': venue.name,
        'alternatives': [{'id': v.id, 'name': v.name, 'capacity': v.capacity} for v in alternatives]
    })


@booking_bp.route('/api/bookings/available-slots', methods=['GET'])
def api_get_available_slots():
    """API endpoint to get available time slots for a venue"""
    venue_id = request.args.get('venue_id', type=int)
    date_str = request.args.get('date')
    duration = request.args.get('duration', 60, type=int)
    
    if not venue_id or not date_str:
        return jsonify({'error': 'Missing required fields'}), 400
    
    target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    slots = VenueService.get_time_slots(venue_id, target_date, duration)
    
    return jsonify({
        'venue_id': venue_id,
        'date': date_str,
        'slots': slots
    })


# ============================================
# Booking Statistics
# ============================================

@booking_bp.route('/stats')
@login_required
def stats():
    """Booking statistics dashboard"""
    if current_user.role != 'admin':
        flash('Access denied', 'danger')
        return redirect(url_for('booking.index'))
    
    # Get statistics
    total_bookings = VenueBooking.query.count()
    active_bookings = VenueBooking.query.filter(
        VenueBooking.start_time <= datetime.utcnow(),
        VenueBooking.end_time >= datetime.utcnow(),
        VenueBooking.status == BookingStatus.CONFIRMED
    ).count()
    
    pending_approvals = VenueBooking.query.filter(
        VenueBooking.status.in_([BookingStatus.PENDING_FACULTY, BookingStatus.PENDING_ADMIN, BookingStatus.PENDING_SECURITY])
    ).count()
    
    completed_today = VenueBooking.query.filter(
        VenueBooking.end_time >= datetime.utcnow().replace(hour=0, minute=0, second=0),
        VenueBooking.end_time <= datetime.utcnow(),
        VenueBooking.status == BookingStatus.COMPLETED
    ).count()
    
    # Weekly bookings
    week_start = datetime.utcnow() - timedelta(days=7)
    weekly_bookings = VenueBooking.query.filter(VenueBooking.created_at >= week_start).count()
    
    # Priority distribution
    priority_stats = PriorityService.get_priority_statistics()
    
    stats = {
        'total': total_bookings,
        'active': active_bookings,
        'pending_approvals': pending_approvals,
        'completed_today': completed_today,
        'weekly': weekly_bookings,
        'priority': priority_stats
    }
    
    return render_template('booking/stats.html', stats=stats)


# ============================================
# Export Functionality
# ============================================

@booking_bp.route('/export')
@login_required
def export():
    """Export bookings to CSV"""
    if current_user.role != 'admin':
        flash('Access denied', 'danger')
        return redirect(url_for('booking.index'))
    
    import csv
    from io import StringIO
    from flask import Response
    
    bookings = VenueBooking.query.order_by(VenueBooking.start_time.desc()).all()
    
    si = StringIO()
    writer = csv.writer(si)
    
    # Write header
    writer.writerow(['ID', 'Title', 'Event Type', 'Venue', 'Start Time', 'End Time', 
                     'Status', 'Priority', 'Expected Attendees', 'Created By', 'Created At'])
    
    # Write data
    for b in bookings:
        writer.writerow([
            b.id,
            b.title,
            b.event_type,
            b.venue.name,
            b.start_time.strftime('%Y-%m-%d %H:%M'),
            b.end_time.strftime('%Y-%m-%d %H:%M'),
            b.status.value,
            b.get_priority_level(),
            b.expected_attendees,
            b.created_by_username if hasattr(b, 'created_by_username') else '',
            b.created_at.strftime('%Y-%m-%d %H:%M')
        ])
    
    output = si.getvalue()
    
    return Response(
        output,
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename=bookings_{datetime.utcnow().strftime("%Y%m%d")}.csv'}
    )