#!/usr/bin/env python
"""
Database initialization script
Creates all database tables and sample data
"""

import sys
import os
from datetime import datetime, timedelta

# Add the parent directory to the path so we can import app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models import User, Event, Team, Score

def init_db():
    """Initialize the database and create all tables"""
    app = create_app()
    
    with app.app_context():
        print("Creating database tables...")
        db.create_all()
        print("OK: Database tables created successfully.")
        
        # Create a default admin user if it doesn't exist
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            print("\nCreating default admin user...")
            admin = User(
                username='admin',
                email='admin@eventx.com',
                role='admin'
            )
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.flush()
            print("OK: Default admin created (username: admin, password: admin123)")
        else:
            print("OK: Admin user already exists")
        
        # Create sample judge user if it doesn't exist
        judge = User.query.filter_by(username='judge1').first()
        if not judge:
            print("\nCreating sample judge user...")
            judge = User(
                username='judge1',
                email='judge1@eventx.com',
                role='judge'
            )
            judge.set_password('judge123')
            db.session.add(judge)
            db.session.flush()
            print("OK: Sample judge created (username: judge1, password: judge123)")
        else:
            print("OK: Judge user already exists")
        
        # Create sample events if they don't exist
        event1 = Event.query.filter_by(name='Web Development Challenge').first()
        if not event1:
            print("\nCreating sample events...")
            event1 = Event(
                name='Web Development Challenge',
                description='Build an innovative web application using modern technologies',
                event_date=datetime.now() + timedelta(days=7),
                venue='Tech Hub, Innovation Park',
                max_teams=50,
                status='upcoming'
            )
            db.session.add(event1)
            db.session.flush()
            print("OK: Web Development Challenge event created")
        
        event2 = Event.query.filter_by(name='AI Innovation Hackathon').first()
        if not event2:
            event2 = Event(
                name='AI Innovation Hackathon',
                description='Create AI-powered solutions to real-world problems',
                event_date=datetime.now() + timedelta(days=14),
                venue='Convention Center, Downtown',
                max_teams=30,
                status='upcoming'
            )
            db.session.add(event2)
            db.session.flush()
            print("OK: AI Innovation Hackathon event created")
        
        event3 = Event.query.filter_by(name='Mobile App Showcase').first()
        if not event3:
            event3 = Event(
                name='Mobile App Showcase',
                description='Showcase your best mobile app projects',
                event_date=datetime.now() + timedelta(days=21),
                venue='Digital Innovation Center',
                max_teams=40,
                status='upcoming'
            )
            db.session.add(event3)
            db.session.flush()
            print("OK: Mobile App Showcase event created")
        
        db.session.commit()
        print("\nOK: Database initialization complete!")
        print("\nDefault Credentials:")
        print("   Admin: username=admin, password=admin123")
        print("   Judge: username=judge1, password=judge123")

if __name__ == '__main__':
    init_db()
