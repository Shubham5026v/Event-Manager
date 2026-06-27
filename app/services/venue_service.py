"""
Venue Service - Venue Management and Availability
Handles venue CRUD operations, availability checking, capacity management, and maintenance scheduling
"""

from datetime import datetime, timedelta, time
from flask import current_app
from app import db
from app.models import Venue, VenueType, VenueStatus, VenueAmenity, VenueMaintenanceSlot
from app.models import VenueBooking, BookingStatus
from sqlalchemy import func, and_, or_

class VenueService:
    """
    Service class for managing venues
    Handles venue CRUD, availability checking, capacity management, and maintenance
    """
    
    # Venue type capacity recommendations
    CAPACITY_RECOMMENDATIONS = {
        VenueType.AUDITORIUM: {'min': 100, 'max': 1000, 'recommended': 300},
        VenueType.GROUND: {'min': 500, 'max': 10000, 'recommended': 2000},
        VenueType.STUDIO: {'min': 10, 'max': 100, 'recommended': 30},
        VenueType.CONFERENCE_HALL: {'min': 20, 'max': 300, 'recommended': 100},
        VenueType.SEMINAR_HALL: {'min': 30, 'max': 200, 'recommended': 80},
        VenueType.OPEN_AIR: {'min': 100, 'max': 5000, 'recommended': 500},
        VenueType.LAB: {'min': 10, 'max': 60, 'recommended': 30}
    }
    
    @classmethod
    def get_all_venues(cls, filters=None):
        """
        Get all venues with optional filters
        
        Args:
            filters: Dictionary of filters (type, status, min_capacity, max_capacity, search)
            
        Returns:
            list: List of venues matching filters
        """
        query = Venue.query
        
        if filters:
            if filters.get('type'):
                query = query.filter(Venue.type == filters['type'])
            if filters.get('status'):
                query = query.filter(Venue.status == filters['status'])
            if filters.get('min_capacity'):
                query = query.filter(Venue.capacity >= filters['min_capacity'])
            if filters.get('max_capacity'):
                query = query.filter(Venue.capacity <= filters['max_capacity'])
            if filters.get('search'):
                search_term = f"%{filters['search']}%"
                query = query.filter(
                    or_(
                        Venue.name.ilike(search_term),
                        Venue.building.ilike(search_term),
                        Venue.description.ilike(search_term)
                    )
                )
            if filters.get('amenities'):
                for amenity in filters['amenities']:
                    query = query.filter(Venue.amenities.contains([amenity]))
        
        return query.order_by(Venue.name).all()
    
    @classmethod
    def get_venue(cls, venue_id):
        """Get a single venue by ID"""
        return Venue.query.get(venue_id)
    
    @classmethod
    def create_venue(cls, data, user_id):
        """Create a new venue"""
        try:
            if not data.get('name'):
                raise ValueError("Venue name is required")
            if not data.get('type'):
                raise ValueError("Venue type is required")
            if not data.get('capacity') or data['capacity'] < 1:
                raise ValueError("Valid capacity is required")
            
            existing = Venue.query.filter_by(name=data['name']).first()
            if existing:
                raise ValueError(f"Venue with name '{data['name']}' already exists")
            
            venue = Venue(
                name=data['name'],
                type=data['type'],
                description=data.get('description', ''),
                capacity=data['capacity'],
                building=data.get('building'),
                floor=data.get('floor'),
                room_number=data.get('room_number'),
                coordinates=data.get('coordinates'),
                opens_at=cls._parse_time(data.get('opens_at', '08:00')),
                closes_at=cls._parse_time(data.get('closes_at', '22:00')),
                base_price=data.get('base_price', 0.0),
                deposit_amount=data.get('deposit_amount', 0.0),
                status=VenueStatus(data.get('status', 'active')),
                amenities=data.get('amenities', []),
                image_url=data.get('image_url'),
                created_by=user_id
            )
            
            db.session.add(venue)
            db.session.commit()
            
            current_app.logger.info(f"Venue created: {venue.id} - {venue.name}")
            return venue
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Venue creation failed: {e}")
            raise
    
    @classmethod
    def update_venue(cls, venue_id, data):
        """Update an existing venue"""
        try:
            venue = Venue.query.get(venue_id)
            if not venue:
                raise ValueError("Venue not found")
            
            if 'name' in data and data['name'] != venue.name:
                existing = Venue.query.filter_by(name=data['name']).first()
                if existing:
                    raise ValueError(f"Venue with name '{data['name']}' already exists")
                venue.name = data['name']
            
            if 'type' in data:
                venue.type = data['type']
            if 'description' in data:
                venue.description = data['description']
            if 'capacity' in data:
                if data['capacity'] < 1:
                    raise ValueError("Capacity must be at least 1")
                venue.capacity = data['capacity']
            if 'building' in data:
                venue.building = data['building']
            if 'floor' in data:
                venue.floor = data['floor']
            if 'room_number' in data:
                venue.room_number = data['room_number']
            if 'coordinates' in data:
                venue.coordinates = data['coordinates']
            if 'opens_at' in data:
                venue.opens_at = cls._parse_time(data['opens_at'])
            if 'closes_at' in data:
                venue.closes_at = cls._parse_time(data['closes_at'])
            if 'base_price' in data:
                venue.base_price = data['base_price']
            if 'deposit_amount' in data:
                venue.deposit_amount = data['deposit_amount']
            if 'status' in data:
                venue.status = VenueStatus(data['status'])
            if 'amenities' in data:
                venue.amenities = data['amenities']
            if 'image_url' in data:
                venue.image_url = data['image_url']
            
            venue.updated_at = datetime.utcnow()
            db.session.commit()
            
            current_app.logger.info(f"Venue updated: {venue.id} - {venue.name}")
            return venue
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Venue update failed: {e}")
            raise
    
    @classmethod
    def delete_venue(cls, venue_id):
        """Delete a venue"""
        venue = Venue.query.get(venue_id)
        if not venue:
            raise ValueError("Venue not found")
        
        active_bookings = VenueBooking.query.filter(
            VenueBooking.venue_id == venue_id,
            VenueBooking.start_time >= datetime.utcnow(),
            VenueBooking.status.in_(['approved', 'confirmed', 'pending_faculty', 'pending_admin', 'pending_security'])
        ).count()
        
        if active_bookings > 0:
            raise ValueError(f"Cannot delete venue with {active_bookings} active bookings")
        
        db.session.delete(venue)
        db.session.commit()
        
        current_app.logger.info(f"Venue deleted: {venue_id}")
        return True
    
    @classmethod
    def get_available_venues(cls, start_time, end_time, venue_type=None, capacity_needed=None, amenities_needed=None):
        """Get all available venues for a given time slot"""
        query = Venue.query.filter(Venue.status == VenueStatus.ACTIVE)
        
        if venue_type:
            query = query.filter(Venue.type == venue_type)
        if capacity_needed:
            query = query.filter(Venue.capacity >= capacity_needed)
        if amenities_needed:
            for amenity in amenities_needed:
                query = query.filter(Venue.amenities.contains([amenity]))
        
        venues = query.all()
        
        available = []
        for venue in venues:
            if venue.is_available(start_time, end_time):
                available.append(venue)
        
        return available
    
    @classmethod
    def get_time_slots(cls, venue_id, target_date, duration_minutes=60):
        """Get available time slots for a venue on a specific date"""
        venue = Venue.query.get(venue_id)
        if not venue:
            return []
        
        opens_at = venue.opens_at if venue.opens_at else time(8, 0)
        closes_at = venue.closes_at if venue.closes_at else time(22, 0)
        
        start_datetime = datetime.combine(target_date, opens_at)
        end_datetime = datetime.combine(target_date, closes_at)
        
        bookings = VenueBooking.query.filter(
            VenueBooking.venue_id == venue_id,
            VenueBooking.status.in_(['approved', 'confirmed']),
            VenueBooking.start_time >= start_datetime,
            VenueBooking.end_time <= end_datetime
        ).order_by(VenueBooking.start_time).all()
        
        slots = []
        current = start_datetime
        slot_duration = timedelta(minutes=duration_minutes)
        
        while current + slot_duration <= end_datetime:
            slot_end = current + slot_duration
            
            available = True
            for booking in bookings:
                if not (booking.end_time <= current or booking.start_time >= slot_end):
                    available = False
                    break
            
            slots.append({
                'start': current,
                'end': slot_end,
                'start_time': current.strftime('%H:%M'),
                'end_time': slot_end.strftime('%H:%M'),
                'available': available
            })
            
            current += slot_duration
        
        return slots
    
    @classmethod
    def get_alternative_times(cls, venue_id, start_time, end_time, max_suggestions=3):
        """Get alternative time suggestions for a venue"""
        venue = Venue.query.get(venue_id)
        if not venue:
            return []
        
        duration = (end_time - start_time).total_seconds() / 3600
        target_date = start_time.date()
        
        opens_at = datetime.combine(target_date, venue.opens_at) if venue.opens_at else None
        closes_at = datetime.combine(target_date, venue.closes_at) if venue.closes_at else None
        
        if not opens_at or not closes_at:
            return []
        
        bookings = VenueBooking.query.filter(
            VenueBooking.venue_id == venue_id,
            VenueBooking.status.in_(['approved', 'confirmed']),
            VenueBooking.start_time >= datetime.combine(target_date, time(0, 0)),
            VenueBooking.end_time <= datetime.combine(target_date, time(23, 59))
        ).order_by(VenueBooking.start_time).all()
        
        alternatives = []
        current = opens_at
        
        for booking in bookings:
            if booking.start_time > current:
                gap_end = booking.start_time
                gap_duration = (gap_end - current).total_seconds() / 3600
                
                if gap_duration >= duration:
                    alternatives.append({
                        'start': current,
                        'end': current + timedelta(hours=duration),
                        'start_time': current.strftime('%H:%M'),
                        'end_time': (current + timedelta(hours=duration)).strftime('%H:%M')
                    })
            
            current = max(current, booking.end_time)
            
            if len(alternatives) >= max_suggestions:
                break
        
        if len(alternatives) < max_suggestions and current + timedelta(hours=duration) <= closes_at:
            alternatives.append({
                'start': current,
                'end': current + timedelta(hours=duration),
                'start_time': current.strftime('%H:%M'),
                'end_time': (current + timedelta(hours=duration)).strftime('%H:%M')
            })
        
        return alternatives[:max_suggestions]
    
    @classmethod
    def get_venue_statistics(cls, venue_id, start_date=None, end_date=None):
        """Get usage statistics for a venue"""
        venue = Venue.query.get(venue_id)
        if not venue:
            return {}
        
        if not start_date:
            start_date = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0)
        if not end_date:
            end_date = start_date + timedelta(days=30)
        
        bookings = VenueBooking.query.filter(
            VenueBooking.venue_id == venue_id,
            VenueBooking.status.in_(['approved', 'confirmed', 'completed']),
            VenueBooking.start_time >= start_date,
            VenueBooking.end_time <= end_date
        ).all()
        
        total_bookings = len(bookings)
        total_hours = sum((b.end_time - b.start_time).total_seconds() / 3600 for b in bookings)
        total_attendees = sum(b.expected_attendees or 0 for b in bookings)
        
        operating_hours_per_day = cls._get_operating_hours_per_day(venue)
        days_in_period = (end_date - start_date).days + 1
        total_available_hours = operating_hours_per_day * days_in_period
        utilization_rate = (total_hours / total_available_hours * 100) if total_available_hours > 0 else 0
        
        return {
            'venue': {'id': venue.id, 'name': venue.name, 'type': venue.type.value, 'capacity': venue.capacity},
            'period': {'start': start_date.isoformat(), 'end': end_date.isoformat()},
            'total_bookings': total_bookings,
            'total_hours': round(total_hours, 1),
            'total_attendees': total_attendees,
            'utilization_rate': round(utilization_rate, 1)
        }
    
    @classmethod
    def add_maintenance_slot(cls, venue_id, start_time, end_time, reason):
        """Add a maintenance slot for a venue"""
        venue = Venue.query.get(venue_id)
        if not venue:
            raise ValueError("Venue not found")
        
        conflicting = VenueBooking.query.filter(
            VenueBooking.venue_id == venue_id,
            VenueBooking.status.in_(['approved', 'confirmed']),
            VenueBooking.start_time < end_time,
            VenueBooking.end_time > start_time
        ).first()
        
        if conflicting:
            raise ValueError(f"Maintenance conflicts with booking: {conflicting.title}")
        
        maintenance = VenueMaintenanceSlot(
            venue_id=venue_id,
            start_time=start_time,
            end_time=end_time,
            reason=reason
        )
        
        db.session.add(maintenance)
        db.session.commit()
        
        return maintenance
    
    @classmethod
    def remove_maintenance_slot(cls, slot_id):
        """Remove a maintenance slot"""
        slot = VenueMaintenanceSlot.query.get(slot_id)
        if not slot:
            raise ValueError("Maintenance slot not found")
        
        db.session.delete(slot)
        db.session.commit()
        return True
    
    @classmethod
    def get_maintenance_slots(cls, venue_id, start_date=None, end_date=None):
        """Get maintenance slots for a venue"""
        query = VenueMaintenanceSlot.query.filter_by(venue_id=venue_id)
        if start_date:
            query = query.filter(VenueMaintenanceSlot.start_time >= start_date)
        if end_date:
            query = query.filter(VenueMaintenanceSlot.end_time <= end_date)
        return query.order_by(VenueMaintenanceSlot.start_time).all()
    
    @classmethod
    def get_venue_amenities_list(cls):
        """Get list of all available amenities"""
        return [
            {'value': 'ac', 'label': 'Air Conditioning', 'icon': 'fa-snowflake'},
            {'value': 'projector', 'label': 'Projector', 'icon': 'fa-video'},
            {'value': 'sound_system', 'label': 'Sound System', 'icon': 'fa-music'},
            {'value': 'stage_lighting', 'label': 'Stage Lighting', 'icon': 'fa-lightbulb'},
            {'value': 'backstage', 'label': 'Backstage Area', 'icon': 'fa-door-open'},
            {'value': 'green_room', 'label': 'Green Room', 'icon': 'fa-couch'},
            {'value': 'parking', 'label': 'Parking', 'icon': 'fa-parking'},
            {'value': 'wifi', 'label': 'WiFi', 'icon': 'fa-wifi'},
            {'value': 'microphones', 'label': 'Microphones', 'icon': 'fa-microphone'},
            {'value': 'podium', 'label': 'Podium', 'icon': 'fa-chalkboard'},
            {'value': 'recording', 'label': 'Recording Equipment', 'icon': 'fa-video'},
            {'value': 'wheelchair_access', 'label': 'Wheelchair Access', 'icon': 'fa-wheelchair'}
        ]
    
    @classmethod
    def get_venue_types(cls):
        """Get list of all venue types"""
        return [
            {'value': 'auditorium', 'label': 'Auditorium', 'icon': 'fa-building'},
            {'value': 'ground', 'label': 'Ground / Field', 'icon': 'fa-tree'},
            {'value': 'studio', 'label': 'Studio', 'icon': 'fa-paint-brush'},
            {'value': 'conference_hall', 'label': 'Conference Hall', 'icon': 'fa-users'},
            {'value': 'seminar_hall', 'label': 'Seminar Hall', 'icon': 'fa-chalkboard-user'},
            {'value': 'open_air', 'label': 'Open Air Theatre', 'icon': 'fa-sun'},
            {'value': 'lab', 'label': 'Laboratory', 'icon': 'fa-flask'}
        ]
    
    @classmethod
    def _parse_time(cls, time_str):
        """Parse time string to time object"""
        if not time_str:
            return None
        try:
            return datetime.strptime(time_str, '%H:%M').time()
        except ValueError:
            return None
    
    @classmethod
    def _get_operating_hours_per_day(cls, venue):
        """Get operating hours per day for a venue"""
        if not venue.opens_at or not venue.closes_at:
            return 14
        open_hour = venue.opens_at.hour + venue.opens_at.minute / 60
        close_hour = venue.closes_at.hour + venue.closes_at.minute / 60
        return close_hour - open_hour