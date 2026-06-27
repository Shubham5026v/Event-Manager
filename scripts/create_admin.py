import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models import User

def create_admin():
    app = create_app()
    with app.app_context():
        # Check if admin already exists
        admin = User.query.filter_by(role='admin').first()
        
        if admin:
            print(f"Admin user already exists: {admin.username}")
            return
        
        # Create admin user
        username = input("Enter admin username (default: admin): ").strip() or "admin"
        email = input("Enter admin email: ").strip()
        password = input("Enter admin password: ").strip()
        
        if not email:
            print("Email is required!")
            return
        if not password:
            print("Password is required!")
            return
        
        admin_user = User(
            username=username,
            email=email,
            role='admin'
        )
        admin_user.set_password(password)
        
        db.session.add(admin_user)
        db.session.commit()
        
        print(f"Admin user '{username}' created successfully!")

if __name__ == '__main__':
    create_admin()