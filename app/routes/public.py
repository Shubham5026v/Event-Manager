from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import Event, Team, Score, ActivityLog
from datetime import datetime

bp = Blueprint('public', __name__)

@bp.route('/')
def index():
    return render_template('index.html')

@bp.route('/live-scoreboard')
def live_scoreboard():
    return render_template('live-scoreboard.html')

@bp.route('/api/events/upcoming')
def upcoming_events():
    events = Event.query.filter(
        Event.event_date >= datetime.now(),
        Event.status == 'upcoming'
    ).order_by(Event.event_date).limit(6).all()
    
    events_data = []
    for event in events:
        events_data.append({
            'id': event.id,
            'name': event.name,
            'description': event.description,
            'event_date': event.event_date.isoformat(),
            'venue': event.venue,
            'status': event.status,
            'teams_count': Team.query.filter_by(event_id=event.id).count()
        })
    
    return jsonify(events_data)

@bp.route('/api/scoreboard/live')
def live_scoreboard_data():
    # Get ongoing events
    ongoing_events = Event.query.filter_by(status='ongoing').all()
    
    scoreboard_data = []
    for event in ongoing_events:
        teams = Team.query.filter_by(event_id=event.id).all()
        event_scores = []
        
        for team in teams:
            scores = Score.query.filter_by(team_id=team.id, event_id=event.id).all()
            total_score = sum(score.score for score in scores) if scores else 0
            
            event_scores.append({
                'team_id': team.id,
                'team_name': team.name,
                'institution': team.institution,
                'total_score': total_score,
                'scores_count': len(scores)
            })
        
        # Sort by total score descending
        event_scores.sort(key=lambda x: x['total_score'], reverse=True)
        
        # Add rankings
        for idx, team in enumerate(event_scores, 1):
            team['rank'] = idx
        
        scoreboard_data.append({
            'event_id': event.id,
            'event_name': event.name,
            'event_date': event.event_date.isoformat(),
            'teams': event_scores
        })
    
    return jsonify(scoreboard_data)

@bp.route('/api/events/ongoing')
def ongoing_events():
    events = Event.query.filter_by(status='ongoing').all()
    
    events_data = []
    for event in events:
        events_data.append({
            'id': event.id,
            'name': event.name,
            'event_date': event.event_date.isoformat(),
            'venue': event.venue,
            'teams_count': Team.query.filter_by(event_id=event.id).count()
        })
    
    return jsonify(events_data)

@bp.route('/api/events/completed')
def completed_events():
    events = Event.query.filter_by(status='completed').order_by(Event.event_date.desc()).limit(10).all()
    
    events_data = []
    for event in events:
        # Get top 3 teams for completed events
        teams = Team.query.filter_by(event_id=event.id).all()
        event_scores = []
        
        for team in teams:
            scores = Score.query.filter_by(team_id=team.id, event_id=event.id).all()
            total_score = sum(score.score for score in scores) if scores else 0
            event_scores.append({
                'team_name': team.name,
                'total_score': total_score
            })
        
        event_scores.sort(key=lambda x: x['total_score'], reverse=True)
        top_3 = event_scores[:3]
        
        events_data.append({
            'id': event.id,
            'name': event.name,
            'event_date': event.event_date.isoformat(),
            'top_teams': top_3
        })
    
    return jsonify(events_data)

@bp.route('/api/admin/dashboard/stats')
def admin_dashboard_stats():
    total_events = Event.query.count()
    total_teams = Team.query.count()
    total_participants = total_teams
    active_events = Event.query.filter(Event.status.in_(['upcoming', 'ongoing'])).count()

    recent_events = Event.query.order_by(Event.event_date.desc()).limit(6).all()
    events_data = []
    for event in recent_events:
        events_data.append({
            'id': event.id,
            'name': event.name,
            'event_date': event.event_date.isoformat(),
            'venue': event.venue,
            'teams_count': Team.query.filter_by(event_id=event.id).count(),
            'status': event.status
        })

    recent_logs = ActivityLog.query.order_by(ActivityLog.created_at.desc()).limit(5).all()
    activity_data = []
    for log in recent_logs:
        activity_data.append({
            'action': log.action,
            'description': log.description or '',
            'time': log.created_at.isoformat(),
            'icon': 'fa-chart-line'
        })

    return jsonify({
        'total_events': total_events,
        'total_teams': total_teams,
        'total_participants': total_participants,
        'active_events': active_events,
        'events': events_data,
        'recent_activity': activity_data
    })

@bp.route('/api/admin/events', methods=['POST'])
@login_required
def admin_create_event():
    if current_user.role != 'admin':
        return jsonify({'error': 'Forbidden'}), 403

    data = request.get_json() or {}
    name = data.get('name')
    description = data.get('description', '')
    event_date_raw = data.get('event_date')
    venue = data.get('venue')

    if not name or not event_date_raw or not venue:
        return jsonify({'error': 'Missing required fields'}), 400

    try:
        event_date = datetime.fromisoformat(event_date_raw)
    except ValueError:
        return jsonify({'error': 'Invalid event_date format'}), 400

    status = 'upcoming' if event_date >= datetime.now() else 'ongoing'
    event = Event(
        name=name,
        description=description,
        event_date=event_date,
        venue=venue,
        status=status
    )

    db.session.add(event)
    db.session.commit()

    return jsonify({'message': 'Event created successfully', 'event_id': event.id}), 201