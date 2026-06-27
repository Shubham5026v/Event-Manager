from functools import wraps
from flask import flash, redirect, url_for
from flask_login import current_user

def login_required(role=None):
    """Decorator to require login and optionally specific role"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Please login to access this page', 'warning')
                return redirect(url_for('auth.login'))
            
            if role and current_user.role != role:
                flash('You do not have permission to access this page', 'danger')
                return redirect(url_for('public.index'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def admin_required(f):
    """Decorator to require admin role"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please login to access this page', 'warning')
            return redirect(url_for('auth.login'))
        
        if current_user.role != 'admin':
            flash('Admin access required', 'danger')
            return redirect(url_for('public.index'))
        
        return f(*args, **kwargs)
    return decorated_function

def judge_required(f):
    """Decorator to require judge role"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please login to access this page', 'warning')
            return redirect(url_for('auth.login'))
        
        if current_user.role != 'judge':
            flash('Judge access required', 'danger')
            return redirect(url_for('public.index'))
        
        return f(*args, **kwargs)
    return decorated_function

def team_required(f):
    """Decorator to require team role"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please login to access this page', 'warning')
            return redirect(url_for('auth.login'))
        
        if current_user.role != 'team':
            flash('Team access required', 'danger')
            return redirect(url_for('public.index'))
        
        return f(*args, **kwargs)
    return decorated_function

def validate_event_dates(event_date):
    """Helper function to validate event dates"""
    from datetime import datetime
    
    if event_date < datetime.now():
        return False, "Event date cannot be in the past"
    return True, None

def calculate_team_score(team_id, event_id):
    """Calculate total score for a team in an event"""
    from app.models import Score
    
    scores = Score.query.filter_by(team_id=team_id, event_id=event_id).all()
    if not scores:
        return 0
    return sum(score.score for score in scores) / len(scores)

def get_team_ranking(event_id):
    """Get ranking of all teams in an event"""
    from app.models import Team, Score
    
    teams = Team.query.filter_by(event_id=event_id).all()
    rankings = []
    
    for team in teams:
        scores = Score.query.filter_by(team_id=team.id, event_id=event_id).all()
        total_score = sum(score.score for score in scores) if scores else 0
        rankings.append({
            'team_id': team.id,
            'team_name': team.name,
            'total_score': total_score,
            'scores_count': len(scores)
        })
    
    rankings.sort(key=lambda x: x['total_score'], reverse=True)
    
    # Add rank
    for idx, team in enumerate(rankings, 1):
        team['rank'] = idx
    
    return rankings