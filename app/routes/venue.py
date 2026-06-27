"""
Venue Routes - Venue Management
Handles venue CRUD operations, availability checking, and venue settings
"""

import os
from datetime import datetime, timedelta, date
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, abort, current_app, send_file
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from app import db
from app.models import Venue, VenueType, VenueStatus, VenueAmenity, VenueMaintenanceSlot, VenueBooking, BookingStatus, User
from app.services.venue_service import VenueService
from app.services.booking_service import BookingService

# Create blueprint
venue_bp = Blueprint('venue', __name__, url_prefix='/venues')


# ============================================
# Venue Management Views
# ============================================

@venue_bp.route('/')
@login_required
def index():
    """List all venues"""
    # Get filter parameters
    venue_type = request.args.get('type')
    status = request.args.get('status')
    search = request.args.get('search')
    capacity_min = request.args.get('capacity_min', type=int)
    capacity_max = request.args.get('capacity_max', type=int)
    
    filters = {}
    if venue_type:
        filters['type'] = venue_type
    if status:
        filters['status'] = status
    if search:
        filters['search'] = search
    if capacity_min:
        filters['min_capacity'] = capacity_min
    if capacity_max:
        filters['max_capacity'] = capacity_max
    
    venues = VenueService.get_all_venues(filters)
    
    # Get statistics
    stats = {
        'total': Venue.query.count(),
        'active': Venue.query.filter_by(status=VenueStatus.ACTIVE).count(),
        'maintenance': Venue.query.filter_by(status=VenueStatus.MAINTENANCE).count(),
        'closed': Venue.query.filter_by(status=VenueStatus.CLOSED).count()
    }
    
    return render_template('venue/index.html', 
                          venues=venues, 
                          stats=stats,
                          types=[t.value for t in VenueType],
                          statuses=[s.value for s in VenueStatus])


@venue_bp.route('/<int:venue_id>')
@login_required
def view(venue_id):
    """View venue details"""
    venue = Venue.query.get_or_404(venue_id)
    
    # Get upcoming bookings for this venue
    upcoming_bookings = VenueBooking.query.filter(
        VenueBooking.venue_id == venue_id,
        VenueBooking.status.in_(['approved', 'confirmed']),
        VenueBooking.start_time >= datetime.utcnow()
    ).order_by(VenueBooking.start_time).limit(10).all()
    
    # Get booking statistics
    total_bookings = VenueBooking.query.filter_by(venue_id=venue_id).count()
    upcoming_count = VenueBooking.query.filter(
        VenueBooking.venue_id == venue_id,
        VenueBooking.start_time >= datetime.utcnow(),
        VenueBooking.status.in_(['approved', 'confirmed'])
    ).count()
    
    # Get maintenance schedule
    maintenance_slots = VenueMaintenanceSlot.query.filter(
        VenueMaintenanceSlot.venue_id == venue_id,
        VenueMaintenanceSlot.start_time >= datetime.utcnow()
    ).order_by(VenueMaintenanceSlot.start_time).all()
    
    return render_template('venue/view.html',
                          venue=venue,
                          upcoming_bookings=upcoming_bookings,
                          total_bookings=total_bookings,
                          upcoming_count=upcoming_count,
                          maintenance_slots=maintenance_slots)


@venue_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    """Create a new venue"""
    if current_user.role != 'admin':
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('venue.index'))
    
    if request.method == 'POST':
        try:
            # Handle image upload
            image_url = None
            if 'image' in request.files:
                file = request.files['image']
                if file and file.filename:
                    filename = secure_filename(f"{request.form.get('name')}_{datetime.utcnow().timestamp()}.jpg")
                    upload_folder = os.path.join(current_app.static_folder, 'images', 'venues')
                    os.makedirs(upload_folder, exist_ok=True)
                    filepath = os.path.join(upload_folder, filename)
                    file.save(filepath)
                    image_url = url_for('static', filename=f'images/venues/{filename}')
            
            data = {
                'name': request.form.get('name'),
                'type': request.form.get('type'),
                'description': request.form.get('description'),
                'capacity': request.form.get('capacity', type=int),
                'building': request.form.get('building'),
                'floor': request.form.get('floor'),
                'room_number': request.form.get('room_number'),
                'coordinates': request.form.get('coordinates'),
                'opens_at': request.form.get('opens_at'),
                'closes_at': request.form.get('closes_at'),
                'base_price': request.form.get('base_price', type=float, default=0.0),
                'deposit_amount': request.form.get('deposit_amount', type=float, default=0.0),
                'status': request.form.get('status', 'active'),
                'amenities': request.form.getlist('amenities'),
                'image_url': image_url
            }
            
            venue = VenueService.create_venue(data, current_user.id)
            flash(f'Venue "{venue.name}" created successfully!', 'success')
            return redirect(url_for('venue.view', venue_id=venue.id))
            
        except Exception as e:
            flash(str(e), 'danger')
    
    return render_template('venue/create.html',
                          types=[t.value for t in VenueType],
                          statuses=[s.value for s in VenueStatus],
                          amenities=[a.value for a in VenueAmenity])


@venue_bp.route('/<int:venue_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(venue_id):
    """Edit venue details"""
    if current_user.role != 'admin':
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('venue.index'))
    
    venue = Venue.query.get_or_404(venue_id)
    
    if request.method == 'POST':
        try:
            data = {
                'name': request.form.get('name'),
                'type': request.form.get('type'),
                'description': request.form.get('description'),
                'capacity': request.form.get('capacity', type=int),
                'building': request.form.get('building'),
                'floor': request.form.get('floor'),
                'room_number': request.form.get('room_number'),
                'coordinates': request.form.get('coordinates'),
                'opens_at': request.form.get('opens_at'),
                'closes_at': request.form.get('closes_at'),
                'base_price': request.form.get('base_price', type=float, default=0.0),
                'deposit_amount': request.form.get('deposit_amount', type=float, default=0.0),
                'status': request.form.get('status'),
                'amenities': request.form.getlist('amenities')
            }
            
            # Handle image upload
            if 'image' in request.files:
                file = request.files['image']
                if file and file.filename:
                    filename = secure_filename(f"{request.form.get('name')}_{datetime.utcnow().timestamp()}.jpg")
                    upload_folder = os.path.join(current_app.static_folder, 'images', 'venues')
                    os.makedirs(upload_folder, exist_ok=True)
                    filepath = os.path.join(upload_folder, filename)
                    file.save(filepath)
                    data['image_url'] = url_for('static', filename=f'images/venues/{filename}')
            
            # Handle image removal
            if request.form.get('remove_image') == '1':
                data['image_url'] = None
            
            venue = VenueService.update_venue(venue_id, data)
            flash(f'Venue "{venue.name}" updated successfully!', 'success')
            return redirect(url_for('venue.view', venue_id=venue.id))
            
        except Exception as e:
            flash(str(e), 'danger')
    
    return render_template('venue/edit.html',
                          venue=venue,
                          types=[t.value for t in VenueType],
                          statuses=[s.value for s in VenueStatus],
                          amenities=[a.value for a in VenueAmenity])


@venue_bp.route('/<int:venue_id>/delete', methods=['POST'])
@login_required
def delete(venue_id):
    """Delete a venue"""
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        VenueService.delete_venue(venue_id)
        flash('Venue deleted successfully', 'success')
    except Exception as e:
        flash(str(e), 'danger')
    
    return redirect(url_for('venue.index'))


# ============================================
# Venue Availability & Scheduling
# ============================================

@venue_bp.route('/<int:venue_id>/availability')
@login_required
def availability(venue_id):
    """Check venue availability"""
    venue = Venue.query.get_or_404(venue_id)
    
    date_str = request.args.get('date')
    if date_str:
        check_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    else:
        check_date = datetime.utcnow().date()
    
    # Get available time slots
    slots = VenueService.get_time_slots(venue_id, check_date)
    
    # Get existing bookings for the day
    bookings = VenueBooking.query.filter(
        VenueBooking.venue_id == venue_id,
        VenueBooking.start_time >= datetime.combine(check_date, datetime.min.time()),
        VenueBooking.end_time <= datetime.combine(check_date, datetime.max.time()),
        VenueBooking.status.in_(['approved', 'confirmed'])
    ).order_by(VenueBooking.start_time).all()
    
    return render_template('venue/availability.html',
                          venue=venue,
                          date=check_date,
                          slots=slots,
                          bookings=bookings)


@venue_bp.route('/<int:venue_id>/schedule')
@login_required
def schedule(venue_id):
    """View venue schedule"""
    venue = Venue.query.get_or_404(venue_id)
    
    week_start_str = request.args.get('week')
    if week_start_str:
        week_start = datetime.strptime(week_start_str, '%Y-%m-%d').date()
    else:
        week_start = datetime.utcnow().date() - timedelta(days=datetime.utcnow().weekday())
    
    week_end = week_start + timedelta(days=6)
    
    # Get bookings for the week
    bookings = VenueBooking.query.filter(
        VenueBooking.venue_id == venue_id,
        VenueBooking.start_time >= datetime.combine(week_start, datetime.min.time()),
        VenueBooking.end_time <= datetime.combine(week_end, datetime.max.time()),
        VenueBooking.status.in_(['approved', 'confirmed'])
    ).order_by(VenueBooking.start_time).all()
    
    # Organize by day
    week_days = []
    for i in range(7):
        day_date = week_start + timedelta(days=i)
        day_bookings = [b for b in bookings if b.start_time.date() == day_date]
        week_days.append({
            'date': day_date,
            'bookings': day_bookings
        })
    
    return render_template('venue/schedule.html',
                          venue=venue,
                          week_start=week_start,
                          week_end=week_end,
                          week_days=week_days)


# ============================================
# Maintenance Management
# ============================================

@venue_bp.route('/<int:venue_id>/maintenance', methods=['GET', 'POST'])
@login_required
def manage_maintenance(venue_id):
    """Manage venue maintenance slots"""
    if current_user.role != 'admin':
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('venue.index'))
    
    venue = Venue.query.get_or_404(venue_id)
    
    if request.method == 'POST':
        try:
            start_date = datetime.strptime(request.form.get('start_date'), '%Y-%m-%d')
            start_time = request.form.get('start_time')
            end_date = datetime.strptime(request.form.get('end_date'), '%Y-%m-%d')
            end_time = request.form.get('end_time')
            reason = request.form.get('reason')
            
            start_datetime = datetime.combine(start_date, datetime.strptime(start_time, '%H:%M').time())
            end_datetime = datetime.combine(end_date, datetime.strptime(end_time, '%H:%M').time())
            
            VenueService.add_maintenance_slot(venue_id, start_datetime, end_datetime, reason)
            flash('Maintenance slot added successfully', 'success')
            
        except Exception as e:
            flash(str(e), 'danger')
    
    # Get upcoming maintenance slots
    maintenance_slots = VenueMaintenanceSlot.query.filter(
        VenueMaintenanceSlot.venue_id == venue_id,
        VenueMaintenanceSlot.end_time >= datetime.utcnow()
    ).order_by(VenueMaintenanceSlot.start_time).all()
    
    return render_template('venue/maintenance.html',
                          venue=venue,
                          maintenance_slots=maintenance_slots)


@venue_bp.route('/maintenance/<int:slot_id>/delete', methods=['POST'])
@login_required
def delete_maintenance_slot(slot_id):
    """Delete a maintenance slot"""
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        VenueService.remove_maintenance_slot(slot_id)
        flash('Maintenance slot deleted successfully', 'success')
    except Exception as e:
        flash(str(e), 'danger')
    
    return redirect(request.referrer or url_for('venue.index'))


# ============================================
# API Endpoints
# ============================================

@venue_bp.route('/api/venues', methods=['GET'])
def api_get_venues():
    """API endpoint to get all venues"""
    venue_type = request.args.get('type')
    status = request.args.get('status')
    min_capacity = request.args.get('min_capacity', type=int)
    
    filters = {}
    if venue_type:
        filters['type'] = venue_type
    if status:
        filters['status'] = status
    if min_capacity:
        filters['min_capacity'] = min_capacity
    
    venues = VenueService.get_all_venues(filters)
    
    return jsonify([{
        'id': v.id,
        'name': v.name,
        'type': v.type.value,
        'capacity': v.capacity,
        'status': v.status.value,
        'building': v.building,
        'floor': v.floor,
        'room_number': v.room_number,
        'amenities': v.amenities,
        'image_url': v.image_url,
        'opens_at': v.opens_at.strftime('%H:%M') if v.opens_at else None,
        'closes_at': v.closes_at.strftime('%H:%M') if v.closes_at else None
    } for v in venues])


@venue_bp.route('/api/venues/<int:venue_id>', methods=['GET'])
def api_get_venue(venue_id):
    """API endpoint to get a single venue"""
    venue = Venue.query.get_or_404(venue_id)
    
    return jsonify({
        'id': venue.id,
        'name': venue.name,
        'type': venue.type.value,
        'description': venue.description,
        'capacity': venue.capacity,
        'status': venue.status.value,
        'building': venue.building,
        'floor': venue.floor,
        'room_number': venue.room_number,
        'coordinates': venue.coordinates,
        'amenities': venue.amenities,
        'image_url': venue.image_url,
        'opens_at': venue.opens_at.strftime('%H:%M') if venue.opens_at else None,
        'closes_at': venue.closes_at.strftime('%H:%M') if venue.closes_at else None,
        'base_price': venue.base_price,
        'deposit_amount': venue.deposit_amount
    })


@venue_bp.route('/api/venues/<int:venue_id>/status', methods=['PATCH'])
@login_required
def api_update_venue_status(venue_id):
    """API endpoint to update venue status"""
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    venue = Venue.query.get_or_404(venue_id)
    data = request.get_json()
    new_status = data.get('status')
    
    if new_status not in [s.value for s in VenueStatus]:
        return jsonify({'error': 'Invalid status'}), 400
    
    venue.status = VenueStatus(new_status)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'venue_id': venue.id,
        'status': venue.status.value
    })


@venue_bp.route('/api/venues/<int:venue_id>/availability', methods=['POST'])
def api_check_availability(venue_id):
    """API endpoint to check venue availability"""
    venue = Venue.query.get_or_404(venue_id)
    data = request.get_json()
    
    start_time = datetime.fromisoformat(data.get('start_time'))
    end_time = datetime.fromisoformat(data.get('end_time'))
    
    available = venue.is_available(start_time, end_time)
    
    return jsonify({
        'available': available,
        'venue_id': venue.id,
        'venue_name': venue.name,
        'start_time': start_time.isoformat(),
        'end_time': end_time.isoformat()
    })


@venue_bp.route('/api/venues/available', methods=['POST'])
def api_get_available_venues():
    """API endpoint to get available venues for a time slot"""
    data = request.get_json()
    
    start_time = datetime.fromisoformat(data.get('start_time'))
    end_time = datetime.fromisoformat(data.get('end_time'))
    venue_type = data.get('venue_type')
    capacity_needed = data.get('capacity_needed')
    
    venues = VenueService.get_available_venues(start_time, end_time, venue_type, capacity_needed)
    
    return jsonify([{
        'id': v.id,
        'name': v.name,
        'type': v.type.value,
        'capacity': v.capacity,
        'amenities': v.amenities,
        'image_url': v.image_url
    } for v in venues])


# ============================================
# Venue Reports
# ============================================

@venue_bp.route('/reports')
@login_required
def reports():
    """Venue usage reports"""
    if current_user.role != 'admin':
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('venue.index'))
    
    # Get date range
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    if start_date:
        start = datetime.strptime(start_date, '%Y-%m-%d')
    else:
        start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0)
    
    if end_date:
        end = datetime.strptime(end_date, '%Y-%m-%d')
    else:
        end = datetime.utcnow()
    
    venues = Venue.query.all()
    venue_stats = []
    
    for venue in venues:
        stats = VenueService.get_venue_statistics(venue.id, start, end)
        venue_stats.append(stats)
    
    # Sort by utilization rate
    venue_stats.sort(key=lambda x: x.get('utilization_rate', 0), reverse=True)
    
    return render_template('venue/reports.html',
                          venue_stats=venue_stats,
                          start_date=start,
                          end_date=end)