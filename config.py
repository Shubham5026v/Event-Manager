import os

class Config:
    SECRET_KEY = 'your-secret-key-here-change-in-production'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///eventx.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Session configuration
    PERMANENT_SESSION_LIFETIME = 86400  # 24 hours
    
    # Pagination
    ITEMS_PER_PAGE = 10
    
    # File upload (if needed later)
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    
    # Futuristic theme settings
    THEME = {
        'primary_color': '#00f3ff',
        'secondary_color': '#ff00f7',
        'background_dark': '#0a0a0f',
        'background_light': '#1a1a2e',
        'text_color': '#ffffff',
        'accent_glow': '0 0 10px rgba(0, 243, 255, 0.5)',
        'gradient_primary': 'linear-gradient(135deg, #00f3ff 0%, #ff00f7 100%)',
        'gradient_card': 'linear-gradient(135deg, rgba(255,255,255,0.1) 0%, rgba(255,255,255,0.05) 100%)'
    }
    
    # Animation settings
    ENABLE_ANIMATIONS = True
    ANIMATION_DURATION = 0.3
    
    # Real-time scoreboard refresh interval (milliseconds)
    SCOREBOARD_REFRESH_INTERVAL = 5000

    # Celery configuration
    CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0')
    CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')