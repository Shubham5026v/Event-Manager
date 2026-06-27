"""
Venue Booking Tables Migration
Adds all venue booking related tables to the database
Run with: flask db upgrade or python -m migrations.add_venue_booking_tables
"""

from datetime import datetime
from flask import current_app
from app import db
from sqlalchemy import Table, Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey, JSON, Enum, Time, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
import enum

# ============================================
# Migration Helper Functions
# ============================================

def table_exists(table_name):
    """Check if a table exists in the database"""
    from sqlalchemy import inspect
    inspector = inspect(db.engine)
    return table_name in inspector.get_table_names()

def column_exists(table_name, column_name):
    """Check if a column exists in a table"""
    from sqlalchemy import inspect
    inspector = inspect(db.engine)
    if table_name not in inspector.get_table_names():
        return False
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns

def upgrade():
    """Create all venue booking tables"""
    
    # ============================================
    # 1. Venue Table
    # ============================================
    if not table_exists('venue'):
        class VenueType(enum.Enum):
            AUDITORIUM = 'auditorium'
            GROUND = 'ground'
            STUDIO = 'studio'
            CONFERENCE_HALL = 'conference_hall'
            SEMINAR_HALL = 'seminar_hall'
            OPEN_AIR = 'open_air'
            LAB = 'lab'

        class VenueStatus(enum.Enum):
            ACTIVE = 'active'
            MAINTENANCE = 'maintenance'
            CLOSED = 'closed'
            UNDER_RENOVATION = 'under_renovation'

        VenueTable = Table(
            'venue', db.metadata,
            Column('id', Integer, primary_key=True),
            Column('name', String(100), nullable=False, unique=True),
            Column('type', Enum(VenueType), nullable=False),
            Column('description', Text),
            Column('capacity', Integer, nullable=False),
            Column('status', Enum(VenueStatus), default=VenueStatus.ACTIVE),
            Column('building', String(100)),
            Column('floor', String(20)),
            Column('room_number', String(20)),
            Column('coordinates', String(50)),
            Column('opens_at', Time),
            Column('closes_at', Time),
            Column('amenities', JSON, default=list),
            Column('base_price', Float, default=0.0),
            Column('deposit_amount', Float, default=0.0),
            Column('image_url', String(500)),
            Column('floor_plan_url', String(500)),
            Column('created_by', Integer, ForeignKey('user.id')),
            Column('created_at', DateTime, default=datetime.utcnow),
            Column('updated_at', DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
        )
        VenueTable.create(db.engine)
        print("✓ Created 'venue' table")

    # ============================================
    # 2. Venue Maintenance Slot Table
    # ============================================
    if not table_exists('venue_maintenance_slot'):
        VenueMaintenanceSlotTable = Table(
            'venue_maintenance_slot', db.metadata,
            Column('id', Integer, primary_key=True),
            Column('venue_id', Integer, ForeignKey('venue.id'), nullable=False),
            Column('start_time', DateTime, nullable=False),
            Column('end_time', DateTime, nullable=False),
            Column('reason', String(200)),
            Column('status', String(20), default='scheduled'),
            Column('created_at', DateTime, default=datetime.utcnow)
        )
        VenueMaintenanceSlotTable.create(db.engine)
        print("✓ Created 'venue_maintenance_slot' table")

    # ============================================
    # 3. Venue Booking Table
    # ============================================
    if not table_exists('venue_booking'):
        class BookingPriority(enum.Enum):
            ACADEMIC = 1
            CULTURAL = 2
            PRACTICE = 3
            ADMIN = 0

        class BookingStatus(enum.Enum):
            DRAFT = 'draft'
            PENDING_FACULTY = 'pending_faculty'
            PENDING_ADMIN = 'pending_admin'
            PENDING_SECURITY = 'pending_security'
            APPROVED = 'approved'
            CONFIRMED = 'confirmed'
            REJECTED = 'rejected'
            CANCELLED = 'cancelled'
            COMPLETED = 'completed'

        VenueBookingTable = Table(
            'venue_booking', db.metadata,
            Column('id', Integer, primary_key=True),
            Column('title', String(200), nullable=False),
            Column('description', Text),
            Column('event_type', String(50)),
            Column('venue_id', Integer, ForeignKey('venue.id'), nullable=False),
            Column('start_time', DateTime, nullable=False),
            Column('end_time', DateTime, nullable=False),
            Column('setup_time', Integer, default=30),
            Column('cleanup_time', Integer, default=30),
            Column('expected_attendees', Integer),
            Column('priority', Integer, default=BookingPriority.PRACTICE.value),
            Column('status', Enum(BookingStatus), default=BookingStatus.DRAFT),
            Column('faculty_approved', Boolean, default=False),
            Column('faculty_approved_at', DateTime),
            Column('faculty_approved_by', Integer, ForeignKey('user.id')),
            Column('admin_approved', Boolean, default=False),
            Column('admin_approved_at', DateTime),
            Column('admin_approved_by', Integer, ForeignKey('user.id')),
            Column('security_approved', Boolean, default=False),
            Column('security_approved_at', DateTime),
            Column('security_approved_by', Integer, ForeignKey('user.id')),
            Column('rejection_reason', Text),
            Column('rejection_stage', String(50)),
            Column('requirements', JSON, default=dict),
            Column('special_requests', Text),
            Column('created_by', Integer, ForeignKey('user.id'), nullable=False),
            Column('created_at', DateTime, default=datetime.utcnow),
            Column('updated_at', DateTime, default=datetime.utcnow, onupdate=datetime.utcnow),
            Column('checked_in_at', DateTime),
            Column('checked_out_at', DateTime),
            Column('security_check_in_by', Integer, ForeignKey('user.id')),
            UniqueConstraint('venue_id', 'start_time', name='unique_venue_booking_slot')
        )
        VenueBookingTable.create(db.engine)
        print("✓ Created 'venue_booking' table")

    # ============================================
    # 4. Venue Booking History Table
    # ============================================
    if not table_exists('venue_booking_history'):
        VenueBookingHistoryTable = Table(
            'venue_booking_history', db.metadata,
            Column('id', Integer, primary_key=True),
            Column('booking_id', Integer, ForeignKey('venue_booking.id'), nullable=False),
            Column('action', String(50)),
            Column('old_status', String(50)),
            Column('new_status', String(50)),
            Column('comment', Text),
            Column('performed_by', Integer, ForeignKey('user.id')),
            Column('performed_at', DateTime, default=datetime.utcnow)
        )
        VenueBookingHistoryTable.create(db.engine)
        print("✓ Created 'venue_booking_history' table")

    # ============================================
    # 5. Venue Approval Request Table
    # ============================================
    if not table_exists('venue_approval_request'):
        VenueApprovalRequestTable = Table(
            'venue_approval_request', db.metadata,
            Column('id', Integer, primary_key=True),
            Column('booking_id', Integer, ForeignKey('venue_booking.id'), nullable=False),
            Column('stage', String(50)),
            Column('approver_id', Integer, ForeignKey('user.id')),
            Column('status', String(20), default='pending'),
            Column('request_date', DateTime, default=datetime.utcnow),
            Column('response_date', DateTime),
            Column('comments', Text),
            Column('notification_sent', Boolean, default=False)
        )
        VenueApprovalRequestTable.create(db.engine)
        print("✓ Created 'venue_approval_request' table")

    # ============================================
    # 6. Venue Approval Rule Table
    # ============================================
    if not table_exists('venue_approval_rule'):
        VenueApprovalRuleTable = Table(
            'venue_approval_rule', db.metadata,
            Column('id', Integer, primary_key=True),
            Column('venue_type', String(50)),
            Column('event_type', String(50)),
            Column('min_attendees', Integer),
            Column('requires_faculty', Boolean, default=True),
            Column('requires_admin', Boolean, default=True),
            Column('requires_security', Boolean, default=True),
            Column('auto_approve_if', String(100)),
            Column('created_at', DateTime, default=datetime.utcnow)
        )
        VenueApprovalRuleTable.create(db.engine)
        print("✓ Created 'venue_approval_rule' table")

    # ============================================
    # 7. Venue Priority Rule Table
    # ============================================
    if not table_exists('venue_priority_rule'):
        VenuePriorityRuleTable = Table(
            'venue_priority_rule', db.metadata,
            Column('id', Integer, primary_key=True),
            Column('event_type', String(50), unique=True, nullable=False),
            Column('priority_level', Integer, nullable=False),
            Column('description', String(200)),
            Column('can_override', Boolean, default=False),
            Column('override_roles', JSON, default=list),
            Column('created_at', DateTime, default=datetime.utcnow)
        )
        VenuePriorityRuleTable.create(db.engine)
        print("✓ Created 'venue_priority_rule' table")

    # ============================================
    # 8. Venue Priority Override Table
    # ============================================
    if not table_exists('venue_priority_override'):
        VenuePriorityOverrideTable = Table(
            'venue_priority_override', db.metadata,
            Column('id', Integer, primary_key=True),
            Column('booking_id', Integer, ForeignKey('venue_booking.id'), nullable=False),
            Column('old_priority', Integer),
            Column('new_priority', Integer),
            Column('reason', Text),
            Column('overridden_by', Integer, ForeignKey('user.id')),
            Column('overridden_at', DateTime, default=datetime.utcnow)
        )
        VenuePriorityOverrideTable.create(db.engine)
        print("✓ Created 'venue_priority_override' table")

    # ============================================
    # 9. Venue Calendar Event Table
    # ============================================
    if not table_exists('venue_calendar_event'):
        VenueCalendarEventTable = Table(
            'venue_calendar_event', db.metadata,
            Column('id', Integer, primary_key=True),
            Column('booking_id', Integer, ForeignKey('venue_booking.id'), nullable=False),
            Column('title', String(200), nullable=False),
            Column('start_time', DateTime, nullable=False),
            Column('end_time', DateTime, nullable=False),
            Column('color', String(7), default='#2b6eff'),
            Column('all_day', Boolean, default=False),
            Column('created_at', DateTime, default=datetime.utcnow)
        )
        VenueCalendarEventTable.create(db.engine)
        print("✓ Created 'venue_calendar_event' table")

    # ============================================
    # 10. Venue Calendar Settings Table
    # ============================================
    if not table_exists('venue_calendar_settings'):
        VenueCalendarSettingsTable = Table(
            'venue_calendar_settings', db.metadata,
            Column('id', Integer, primary_key=True),
            Column('user_id', Integer, ForeignKey('user.id'), nullable=False, unique=True),
            Column('default_view', String(20), default='month'),
            Column('show_weekends', Boolean, default=True),
            Column('working_hours_start', Time, default='08:00:00'),
            Column('working_hours_end', Time, default='20:00:00'),
            Column('created_at', DateTime, default=datetime.utcnow),
            Column('updated_at', DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
        )
        VenueCalendarSettingsTable.create(db.engine)
        print("✓ Created 'venue_calendar_settings' table")

    print("\n✅ All venue booking tables created successfully!")


def downgrade():
    """Drop all venue booking tables"""
    
    tables_to_drop = [
        'venue_calendar_settings',
        'venue_calendar_event',
        'venue_priority_override',
        'venue_priority_rule',
        'venue_approval_rule',
        'venue_approval_request',
        'venue_booking_history',
        'venue_booking',
        'venue_maintenance_slot',
        'venue'
    ]
    
    for table_name in tables_to_drop:
        if table_exists(table_name):
            Table(table_name, db.metadata).drop(db.engine)
            print(f"✓ Dropped '{table_name}' table")
    
    print("\n✅ All venue booking tables dropped successfully!")


# ============================================
# Seed Data for Development
# ============================================

def seed_default_approval_rules():
    """Seed default approval rules for development"""
    
    from models.venue_approval import VenueApprovalRule
    
    default_rules = [
        {'venue_type': 'auditorium', 'event_type': 'academic', 'requires_faculty': True, 'requires_admin': True, 'requires_security': True, 'auto_approve_if': 'attendees < 50'},
        {'venue_type': 'auditorium', 'event_type': 'cultural', 'requires_faculty': True, 'requires_admin': True, 'requires_security': True, 'auto_approve_if': None},
        {'venue_type': 'auditorium', 'event_type': 'practice', 'requires_faculty': False, 'requires_admin': True, 'requires_security': True, 'auto_approve_if': None},
        {'venue_type': 'ground', 'event_type': 'academic', 'requires_faculty': True, 'requires_admin': True, 'requires_security': False, 'auto_approve_if': 'attendees < 100'},
        {'venue_type': 'ground', 'event_type': 'cultural', 'requires_faculty': True, 'requires_admin': True, 'requires_security': True, 'auto_approve_if': None},
        {'venue_type': 'studio', 'event_type': 'practice', 'requires_faculty': False, 'requires_admin': False, 'requires_security': False, 'auto_approve_if': 'attendees < 20'},
    ]
    
    for rule_data in default_rules:
        existing = VenueApprovalRule.query.filter_by(
            venue_type=rule_data['venue_type'],
            event_type=rule_data['event_type']
        ).first()
        if not existing:
            rule = VenueApprovalRule(**rule_data)
            db.session.add(rule)
    
    db.session.commit()
    print("✓ Seeded default approval rules")


def seed_default_priority_rules():
    """Seed default priority rules for development"""
    
    from models.venue_priority import VenuePriorityRule
    
    default_priorities = [
        {'event_type': 'exam', 'priority_level': 1, 'description': 'Academic examinations', 'can_override': False},
        {'event_type': 'lecture', 'priority_level': 1, 'description': 'Academic lectures', 'can_override': False},
        {'event_type': 'seminar', 'priority_level': 1, 'description': 'Academic seminars', 'can_override': False},
        {'event_type': 'workshop', 'priority_level': 1, 'description': 'Educational workshops', 'can_override': False},
        {'event_type': 'conference', 'priority_level': 1, 'description': 'Academic conferences', 'can_override': False},
        {'event_type': 'festival', 'priority_level': 2, 'description': 'Cultural festivals', 'can_override': False},
        {'event_type': 'concert', 'priority_level': 2, 'description': 'Cultural concerts', 'can_override': False},
        {'event_type': 'drama', 'priority_level': 2, 'description': 'Dramatics performances', 'can_override': False},
        {'event_type': 'rehearsal', 'priority_level': 3, 'description': 'Practice rehearsals', 'can_override': True},
        {'event_type': 'practice', 'priority_level': 3, 'description': 'Practice sessions', 'can_override': True},
        {'event_type': 'meeting', 'priority_level': 3, 'description': 'General meetings', 'can_override': True},
    ]
    
    for priority_data in default_priorities:
        existing = VenuePriorityRule.query.filter_by(event_type=priority_data['event_type']).first()
        if not existing:
            rule = VenuePriorityRule(**priority_data)
            db.session.add(rule)
    
    db.session.commit()
    print("✓ Seeded default priority rules")


def seed_demo_venues():
    """Seed demo venues for development"""
    
    from models.venue import Venue, VenueType, VenueStatus
    from datetime import time
    
    demo_venues = [
        {
            'name': 'Main Auditorium',
            'type': VenueType.AUDITORIUM,
            'description': 'Large auditorium with state-of-the-art facilities, perfect for conferences, seminars, and cultural events.',
            'capacity': 500,
            'building': 'Academic Block',
            'floor': 'Ground Floor',
            'room_number': 'A-001',
            'opens_at': time(8, 0),
            'closes_at': time(22, 0),
            'amenities': ['ac', 'projector', 'sound_system', 'stage_lighting', 'backstage', 'wifi', 'microphones', 'podium'],
            'base_price': 5000.0,
            'deposit_amount': 10000.0,
            'status': VenueStatus.ACTIVE
        },
        {
            'name': 'Open Ground',
            'type': VenueType.GROUND,
            'description': 'Spacious outdoor ground suitable for sports events, fests, and large gatherings.',
            'capacity': 2000,
            'building': 'Sports Complex',
            'opens_at': time(6, 0),
            'closes_at': time(20, 0),
            'amenities': ['parking', 'sound_system'],
            'base_price': 3000.0,
            'deposit_amount': 5000.0,
            'status': VenueStatus.ACTIVE
        },
        {
            'name': 'Dance Studio',
            'type': VenueType.STUDIO,
            'description': 'Professional dance studio with mirrors, sprung floor, and sound system.',
            'capacity': 50,
            'building': 'Cultural Center',
            'floor': '2nd Floor',
            'room_number': 'C-201',
            'opens_at': time(8, 0),
            'closes_at': time(21, 0),
            'amenities': ['ac', 'sound_system', 'wifi'],
            'base_price': 1000.0,
            'deposit_amount': 2000.0,
            'status': VenueStatus.ACTIVE
        },
        {
            'name': 'Conference Hall',
            'type': VenueType.CONFERENCE_HALL,
            'description': 'Modern conference hall with video conferencing facilities.',
            'capacity': 150,
            'building': 'Admin Block',
            'floor': '1st Floor',
            'room_number': 'B-101',
            'opens_at': time(9, 0),
            'closes_at': time(18, 0),
            'amenities': ['ac', 'projector', 'sound_system', 'wifi', 'microphones', 'podium'],
            'base_price': 2500.0,
            'deposit_amount': 5000.0,
            'status': VenueStatus.ACTIVE
        },
        {
            'name': 'Seminar Hall',
            'type': VenueType.SEMINAR_HALL,
            'description': 'Small seminar hall for academic sessions and workshops.',
            'capacity': 80,
            'building': 'Academic Block',
            'floor': '2nd Floor',
            'room_number': 'A-203',
            'opens_at': time(8, 0),
            'closes_at': time(20, 0),
            'amenities': ['ac', 'projector', 'wifi', 'microphones'],
            'base_price': 1500.0,
            'deposit_amount': 3000.0,
            'status': VenueStatus.ACTIVE
        },
        {
            'name': 'Open Air Theatre',
            'type': VenueType.OPEN_AIR,
            'description': 'Amphitheatre-style open air venue for performances and events.',
            'capacity': 800,
            'building': 'Cultural Complex',
            'opens_at': time(16, 0),
            'closes_at': time(22, 0),
            'amenities': ['stage_lighting', 'sound_system', 'backstage'],
            'base_price': 4000.0,
            'deposit_amount': 8000.0,
            'status': VenueStatus.ACTIVE
        }
    ]
    
    for venue_data in demo_venues:
        existing = Venue.query.filter_by(name=venue_data['name']).first()
        if not existing:
            venue = Venue(**venue_data)
            db.session.add(venue)
    
    db.session.commit()
    print("✓ Seeded demo venues")


def run_seed():
    """Run all seed data functions"""
    with current_app.app_context():
        seed_default_approval_rules()
        seed_default_priority_rules()
        seed_demo_venues()
    print("\n✅ All seed data inserted successfully!")


# ============================================
# Main Execution
# ============================================

if __name__ == '__main__':
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    from app import create_app
    app = create_app()
    
    with app.app_context():
        if len(sys.argv) > 1:
            if sys.argv[1] == 'upgrade':
                upgrade()
            elif sys.argv[1] == 'downgrade':
                downgrade()
            elif sys.argv[1] == 'seed':
                run_seed()
            else:
                print("Usage: python add_venue_booking_tables.py [upgrade|downgrade|seed]")
        else:
            print("Usage: python add_venue_booking_tables.py [upgrade|downgrade|seed]")