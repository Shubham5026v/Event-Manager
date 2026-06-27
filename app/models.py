"""
EventX - Complete Models
Includes User, Event, Team, Score models and Venue Booking Module
"""

from app import db
from datetime import datetime, time
from enum import Enum
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin

# ============================================
# Core EventX Models
# ============================================

class User(UserMixin, db.Model):
    """User model for authentication and authorization"""
    __tablename__ = 'user'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    role = db.Column(db.String(20), nullable=False, default='team')  # admin, judge, team
    
    # Relationships
    teams = db.relationship('Team', backref='user', lazy=True)
    scores = db.relationship('Score', backref='judge', lazy=True)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<User {self.username}>'


class Event(db.Model):
    """Event model for competitions"""
    __tablename__ = 'event'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    event_date = db.Column(db.DateTime, nullable=False)
    venue = db.Column(db.String(200), nullable=False)
    max_teams = db.Column(db.Integer, nullable=False, default=10)
    status = db.Column(db.String(20), nullable=False, default='upcoming')  # upcoming, ongoing, completed
    
    # Relationships
    teams = db.relationship('Team', backref='event', lazy=True)
    scores = db.relationship('Score', backref='event', lazy=True)
    
    def __repr__(self):
        return f'<Event {self.name}>'


class Team(db.Model):
    """Team model for participants"""
    __tablename__ = 'team'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    institution = db.Column(db.String(200), nullable=False)
    leader_name = db.Column(db.String(100), nullable=False)
    leader_email = db.Column(db.String(120), nullable=False)
    leader_phone = db.Column(db.String(20), nullable=False)
    
    # Final results
    final_score = db.Column(db.Float, default=0.0)
    final_rank = db.Column(db.Integer)
    
    # Foreign keys
    event_id = db.Column(db.Integer, db.ForeignKey('event.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Relationships
    scores = db.relationship('Score', backref='team', lazy=True)
    
    def __repr__(self):
        return f'<Team {self.name}>'


class Score(db.Model):
    """Score model for judging"""
    __tablename__ = 'score'
    
    id = db.Column(db.Integer, primary_key=True)
    score = db.Column(db.Float, nullable=False)
    criteria = db.Column(db.String(50), nullable=False)  # creativity, execution, technical, impact, overall
    comments = db.Column(db.Text)
    
    # Foreign keys
    team_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=False)
    event_id = db.Column(db.Integer, db.ForeignKey('event.id'), nullable=False)
    judge_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    def __repr__(self):
        return f'<Score {self.score} for Team {self.team_id}>'


# ============================================
# Certificate Models
# ============================================

class Certificate(db.Model):
    """Certificate model for generated certificates"""
    __tablename__ = 'certificate'
    
    id = db.Column(db.Integer, primary_key=True)
    verification_code = db.Column(db.String(50), unique=True, nullable=False)
    certificate_type = db.Column(db.String(20), nullable=False)  # winner, participation
    filename = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    is_verified = db.Column(db.Boolean, default=False)
    verified_at = db.Column(db.DateTime)
    
    # Certificate details
    rank_position = db.Column(db.Integer)  # 1, 2, 3 for winners
    final_score = db.Column(db.Float)
    custom_message = db.Column(db.Text)
    
    # Metadata
    ip_address = db.Column(db.String(45))  # IPv4/IPv6
    generated_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Foreign keys
    team_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=False)
    event_id = db.Column(db.Integer, db.ForeignKey('event.id'), nullable=False)
    generated_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Relationships
    team = db.relationship('Team', backref='certificates')
    event = db.relationship('Event', backref='certificates')
    generated_by = db.relationship('User', backref='generated_certificates')
    
    def mark_as_verified(self):
        self.is_verified = True
        self.verified_at = datetime.utcnow()
    
    def __repr__(self):
        return f'<Certificate {self.verification_code}>'


class CertificateBatch(db.Model):
    """Batch record for certificate generation"""
    __tablename__ = 'certificate_batch'
    
    id = db.Column(db.Integer, primary_key=True)
    batch_code = db.Column(db.String(100), unique=True, nullable=False)
    total_teams = db.Column(db.Integer, nullable=False)
    generated_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Foreign keys
    event_id = db.Column(db.Integer, db.ForeignKey('event.id'), nullable=False)
    generated_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Relationships
    event = db.relationship('Event', backref='certificate_batches')
    generated_by = db.relationship('User', backref='certificate_batches')
    
    def __repr__(self):
        return f'<CertificateBatch {self.batch_code}>'


class CertificateTemplate(db.Model):
    """Certificate template configurations"""
    __tablename__ = 'certificate_template'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    template_type = db.Column(db.String(20), nullable=False)  # winner, participation
    
    # Styling
    background_color = db.Column(db.String(7), default='#ffffff')
    border_color = db.Column(db.String(7), default='#2b6eff')
    title_color = db.Column(db.String(7), default='#ffaa33')
    text_color = db.Column(db.String(7), default='#000000')
    
    # Features
    has_border = db.Column(db.Boolean, default=True)
    has_seal = db.Column(db.Boolean, default=True)
    has_qr_code = db.Column(db.Boolean, default=True)
    is_default = db.Column(db.Boolean, default=False)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<CertificateTemplate {self.name}>'


class ActivityLog(db.Model):
    """Activity logging for audit trail"""
    __tablename__ = 'activity_log'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    action = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text)
    ip_address = db.Column(db.String(45))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship
    user = db.relationship('User', backref='activity_logs')
    
    def __repr__(self):
        return f'<ActivityLog {self.action}>'


# ============================================
# Venue Core Models
# ============================================

class VenueType(Enum):
    AUDITORIUM = 'auditorium'
    GROUND = 'ground'
    STUDIO = 'studio'
    CONFERENCE_HALL = 'conference_hall'
    SEMINAR_HALL = 'seminar_hall'
    OPEN_AIR = 'open_air'
    LAB = 'lab'


class VenueStatus(Enum):
    ACTIVE = 'active'
    MAINTENANCE = 'maintenance'
    CLOSED = 'closed'
    UNDER_RENOVATION = 'under_renovation'


class VenueAmenity(Enum):
    AC = 'ac'
    PROJECTOR = 'projector'
    SOUND_SYSTEM = 'sound_system'
    STAGE_LIGHTING = 'stage_lighting'
    BACKSTAGE = 'backstage'
    GREEN_ROOM = 'green_room'
    PARKING = 'parking'
    WIFI = 'wifi'
    MICROPHONES = 'microphones'
    PODIUM = 'podium'
    RECORDING = 'recording'


class Venue(db.Model):
    """Venue master table - Auditorium / Ground / Studios"""
    __tablename__ = 'venue'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    type = db.Column(db.Enum(VenueType), nullable=False)
    description = db.Column(db.Text)
    capacity = db.Column(db.Integer, nullable=False)
    status = db.Column(db.Enum(VenueStatus), default=VenueStatus.ACTIVE)
    
    # Location details
    building = db.Column(db.String(100))
    floor = db.Column(db.String(20))
    room_number = db.Column(db.String(20))
    coordinates = db.Column(db.String(50))
    
    # Operating hours
    opens_at = db.Column(db.Time, default=time(8, 0))
    closes_at = db.Column(db.Time, default=time(22, 0))
    
    # Amenities (JSON array)
    amenities = db.Column(db.JSON, default=list)
    
    # Pricing
    base_price = db.Column(db.Float, default=0.0)
    deposit_amount = db.Column(db.Float, default=0.0)
    
    # Media
    image_url = db.Column(db.String(500))
    floor_plan_url = db.Column(db.String(500))
    
    # Metadata
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    bookings = db.relationship('VenueBooking', backref='venue', lazy=True)
    maintenance_slots = db.relationship('VenueMaintenanceSlot', backref='venue', lazy=True)
    
    def is_available(self, start_time, end_time, exclude_booking_id=None):
        """Check if venue is available for given time slot"""
        query = VenueBooking.query.filter(
            VenueBooking.venue_id == self.id,
            VenueBooking.status.in_(['approved', 'confirmed']),
            VenueBooking.start_time < end_time,
            VenueBooking.end_time > start_time
        )
        if exclude_booking_id:
            query = query.filter(VenueBooking.id != exclude_booking_id)
        return query.first() is None
    
    def get_amenities_list(self):
        return [VenueAmenity(a).value for a in self.amenities]
    
    def __repr__(self):
        return f'<Venue {self.name}>'


class VenueMaintenanceSlot(db.Model):
    """Maintenance schedule for venues"""
    __tablename__ = 'venue_maintenance_slot'
    
    id = db.Column(db.Integer, primary_key=True)
    venue_id = db.Column(db.Integer, db.ForeignKey('venue.id'), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    reason = db.Column(db.String(200))
    status = db.Column(db.String(20), default='scheduled')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Maintenance {self.venue.name}>'


# ============================================
# Venue Booking Models
# ============================================

class BookingPriority(Enum):
    ACADEMIC = 1      # Highest priority
    CULTURAL = 2      # Medium priority
    PRACTICE = 3      # Lowest priority
    ADMIN = 0         # Super priority


class BookingStatus(Enum):
    DRAFT = 'draft'
    PENDING_FACULTY = 'pending_faculty'
    PENDING_ADMIN = 'pending_admin'
    PENDING_SECURITY = 'pending_security'
    APPROVED = 'approved'
    CONFIRMED = 'confirmed'
    REJECTED = 'rejected'
    CANCELLED = 'cancelled'
    COMPLETED = 'completed'


class VenueBooking(db.Model):
    """Booking records for venues with approval workflow"""
    __tablename__ = 'venue_booking'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Basic info
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    event_type = db.Column(db.String(50))  # academic, cultural, practice
    
    # Venue and time
    venue_id = db.Column(db.Integer, db.ForeignKey('venue.id'), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    setup_time = db.Column(db.Integer, default=30)
    cleanup_time = db.Column(db.Integer, default=30)
    
    # Capacity
    expected_attendees = db.Column(db.Integer)
    
    # Priority (Academic > Cultural > Practice)
    priority = db.Column(db.Integer, default=BookingPriority.PRACTICE.value)
    
    # Status
    status = db.Column(db.Enum(BookingStatus), default=BookingStatus.DRAFT)
    
    # Multi-level approvals (Faculty → Admin → Security)
    faculty_approved = db.Column(db.Boolean, default=False)
    faculty_approved_at = db.Column(db.DateTime)
    faculty_approved_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    admin_approved = db.Column(db.Boolean, default=False)
    admin_approved_at = db.Column(db.DateTime)
    admin_approved_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    security_approved = db.Column(db.Boolean, default=False)
    security_approved_at = db.Column(db.DateTime)
    security_approved_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    rejection_reason = db.Column(db.Text)
    rejection_stage = db.Column(db.String(50))
    
    # Additional requirements
    requirements = db.Column(db.JSON, default=dict)
    special_requests = db.Column(db.Text)
    
    # Audit
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Check-in/out (Security)
    checked_in_at = db.Column(db.DateTime)
    checked_out_at = db.Column(db.DateTime)
    security_check_in_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    # Relationships
    approval_requests = db.relationship('VenueApprovalRequest', backref='booking', lazy=True)
    history = db.relationship('VenueBookingHistory', backref='booking', lazy=True)
    
    def get_priority_level(self):
        if self.priority == BookingPriority.ACADEMIC.value:
            return 'Academic (High)'
        elif self.priority == BookingPriority.CULTURAL.value:
            return 'Cultural (Medium)'
        elif self.priority == BookingPriority.PRACTICE.value:
            return 'Practice (Low)'
        return 'Admin (Highest)'
    
    def is_approved(self):
        return self.faculty_approved and self.admin_approved and self.security_approved
    
    def get_current_approval_stage(self):
        if not self.faculty_approved:
            return 'Faculty'
        elif not self.admin_approved:
            return 'Admin'
        elif not self.security_approved:
            return 'Security'
        return 'Completed'
    
    def can_cancel(self):
        return self.status not in [BookingStatus.COMPLETED]
    
    def __repr__(self):
        return f'<VenueBooking {self.title}>'


class VenueBookingHistory(db.Model):
    """Audit trail for bookings"""
    __tablename__ = 'venue_booking_history'
    
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('venue_booking.id'), nullable=False)
    action = db.Column(db.String(50))
    old_status = db.Column(db.String(50))
    new_status = db.Column(db.String(50))
    comment = db.Column(db.Text)
    performed_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    performed_at = db.Column(db.DateTime, default=datetime.utcnow)


# ============================================
# Venue Approval Models
# ============================================

class VenueApprovalRequest(db.Model):
    """Approval request tracking for multi-level workflow"""
    __tablename__ = 'venue_approval_request'
    
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('venue_booking.id'), nullable=False)
    stage = db.Column(db.String(50))  # faculty, admin, security
    approver_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    status = db.Column(db.String(20), default='pending')
    request_date = db.Column(db.DateTime, default=datetime.utcnow)
    response_date = db.Column(db.DateTime)
    comments = db.Column(db.Text)
    notification_sent = db.Column(db.Boolean, default=False)
    
    approver = db.relationship('User', foreign_keys=[approver_id])
    
    def __repr__(self):
        return f'<VenueApprovalRequest {self.stage}>'


class VenueApprovalRule(db.Model):
    """Rules for approval workflow"""
    __tablename__ = 'venue_approval_rule'
    
    id = db.Column(db.Integer, primary_key=True)
    venue_type = db.Column(db.String(50))
    event_type = db.Column(db.String(50))
    min_attendees = db.Column(db.Integer)
    requires_faculty = db.Column(db.Boolean, default=True)
    requires_admin = db.Column(db.Boolean, default=True)
    requires_security = db.Column(db.Boolean, default=True)
    auto_approve_if = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<VenueApprovalRule {self.venue_type}>'


# ============================================
# Venue Priority Models
# ============================================

class VenuePriorityRule(db.Model):
    """Priority rules for different event types (Academic > Cultural > Practice)"""
    __tablename__ = 'venue_priority_rule'
    
    id = db.Column(db.Integer, primary_key=True)
    event_type = db.Column(db.String(50), unique=True, nullable=False)
    priority_level = db.Column(db.Integer, nullable=False)
    description = db.Column(db.String(200))
    can_override = db.Column(db.Boolean, default=False)
    override_roles = db.Column(db.JSON, default=list)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<VenuePriorityRule {self.event_type}>'


class VenuePriorityOverride(db.Model):
    """Track priority overrides"""
    __tablename__ = 'venue_priority_override'
    
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('venue_booking.id'), nullable=False)
    old_priority = db.Column(db.Integer)
    new_priority = db.Column(db.Integer)
    reason = db.Column(db.Text)
    overridden_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    overridden_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    booking = db.relationship('VenueBooking', backref='priority_overrides')


# ============================================
# Venue Calendar Models
# ============================================

class VenueCalendarEvent(db.Model):
    """Calendar events for venue booking visualization"""
    __tablename__ = 'venue_calendar_event'
    
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('venue_booking.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    color = db.Column(db.String(7), default='#2b6eff')
    all_day = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    booking = db.relationship('VenueBooking', backref='calendar_event')


class VenueCalendarSettings(db.Model):
    """User-specific calendar settings"""
    __tablename__ = 'venue_calendar_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    default_view = db.Column(db.String(20), default='month')  # month, week, day
    show_weekends = db.Column(db.Boolean, default=True)
    working_hours_start = db.Column(db.Time, default=time(8, 0))
    working_hours_end = db.Column(db.Time, default=time(20, 0))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = db.relationship('User', backref='calendar_settings')