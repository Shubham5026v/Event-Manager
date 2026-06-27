"""
Package initializer for Event Manager route modules.
"""

from .auth import bp as auth_bp
from .admin import bp as admin_bp
from .judge import bp as judge_bp
from .team import bp as team_bp
from .public import bp as public_bp
from .certificate import certificates_bp
from .booking import booking_bp
from .calendar import calendar_bp
from .approval import approval_bp
from .venue import venue_bp

__all__ = [
    'auth_bp',
    'admin_bp',
    'judge_bp',
    'team_bp',
    'public_bp',
    'certificates_bp',
    'booking_bp',
    'calendar_bp',
    'approval_bp',
    'venue_bp',
]
