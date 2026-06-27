from app import create_app
from app import db
from app.models import User, Event, Team, Score

app = create_app()

@app.shell_context_processor
def make_shell_context():
    return {
        'db': db,
        'User': User,
        'Event': Event,
        'Team': Team,
        'Score': Score
    }

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)