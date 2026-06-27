# 🎪 Event Manager

> A Flask-based Event Management System for managing events, teams, judges, venue bookings, approval workflows, certificates, and live scoreboards through a centralized web application.

Designed for **college events, hackathons, competitions, seminars, workshops**, and institutional event workflows — where admins, teams, judges, and public users each get their own dedicated dashboard.

---

## ✨ Features

### 🛠️ Admin Dashboard
- Manage events, teams, judges, and scores
- Control event-related workflows
- Handle certificate generation
- Manage venue booking approvals
- Monitor live scoreboard data
- Access team and judge records from one central place

### 🔐 Authentication
- User login system
- Team registration
- Judge registration
- Role-based dashboard routing for admin, team, judge, and public users

### 👥 Team Module
- Team dashboard
- Event participation workflow
- View certificates
- Track team-related event information

### ⚖️ Judge Module
- Judge dashboard
- Evaluation panel
- Score submission and management
- Competition judging workflow

### 🏛️ Venue Booking System
- Create venue booking requests
- View and edit booking details
- Track booking status
- View personal bookings
- Check venue availability
- Booking approval queue for admin/venue authority
- Booking history and calendar support

### 🏆 Certificate System
- Generate, preview, and download certificates
- Public certificate verification
- Winner and participation certificate support
- Custom certificate assets (background, border, badge, seal)

### 🌐 Public Pages
- Public home page
- Live scoreboard
- Certificate verification, view, and download

---

## 🧰 Tech Stack

| Category       | Technology                          |
|----------------|-------------------------------------|
| Backend        | Python, Flask                       |
| Frontend       | HTML, CSS, JavaScript, Jinja2       |
| Database       | SQLite                              |
| ORM            | SQLAlchemy / Flask-SQLAlchemy       |
| Authentication | Flask-Login                         |
| Forms          | Flask-WTF / WTForms                 |
| Migrations     | Flask-Migrate / Alembic             |
| Certificates   | ReportLab / Pillow                  |
| Deployment     | Render, Railway, PythonAnywhere, VPS|

---

## 📁 Project Structure

```
Event Manager/
│
├── app/
│   ├── __init__.py
│   ├── forms.py
│   ├── models.py
│   ├── utils.py
│   │
│   ├── routes/
│   │   ├── admin.py
│   │   ├── approval.py
│   │   ├── auth.py
│   │   ├── booking.py
│   │   ├── calendar.py
│   │   ├── certificate.py
│   │   ├── judge.py
│   │   ├── public.py
│   │   ├── team.py
│   │   ├── venue.py
│   │   └── __init__.py
│   │
│   ├── services/
│   │   ├── approval_service.py
│   │   ├── booking_service.py
│   │   ├── calendar_service.py
│   │   ├── certificate_generator.py
│   │   ├── notification_service.py
│   │   ├── priority_service.py
│   │   └── venue_service.py
│   │
│   ├── static/
│   │   ├── css/
│   │   │   ├── certificates.css
│   │   │   ├── style.css
│   │   │   └── venue.css
│   │   ├── fonts/
│   │   │   ├── GreatVibes-Regular.ttf
│   │   │   ├── Montserrat-Bold.ttf
│   │   │   └── OpenSans-Regular.ttf
│   │   ├── images/
│   │   │   └── certificates/
│   │   │       ├── background.jpg
│   │   │       ├── border.png
│   │   │       ├── participation_badge.png
│   │   │       ├── seal.png
│   │   │       └── winner_badge.png
│   │   └── js/
│   │       ├── approval_workflow.js
│   │       ├── availability_checker.js
│   │       ├── calendar.js
│   │       ├── certificates.js
│   │       ├── main.js
│   │       └── venue.js
│   │
│   ├── tasks/
│   │   ├── certificate_tasks.py
│   │   └── venue_tasks.py
│   │
│   └── templates/
│       ├── base.html
│       ├── index.html
│       ├── live-scoreboard.html
│       ├── login.html
│       ├── admin/
│       │   ├── dashboard.html
│       │   ├── events.html
│       │   ├── scores.html
│       │   ├── teams.html
│       │   └── certificates/
│       │       ├── generate.html
│       │       ├── index.html
│       │       └── preview.html
│       ├── auth/
│       │   ├── register_judge.html
│       │   └── register_team.html
│       ├── booking/
│       │   ├── create.html
│       │   ├── edit.html
│       │   ├── index.html
│       │   ├── my_bookings.html
│       │   ├── stats.html
│       │   └── view.html
│       ├── judge/
│       │   ├── dashboard.html
│       │   └── panel.html
│       ├── public/
│       │   └── certificates/
│       │       ├── download.html
│       │       ├── verify.html
│       │       └── view.html
│       ├── team/
│       │   ├── certificates.html
│       │   └── dashboard.html
│       └── venue/
│           ├── approval_history.html
│           ├── approval_queue.html
│           ├── availability.html
│           ├── booking_calendar.html
│           ├── booking_detail.html
│           ├── create_booking.html
│           └── index.html
│
├── migrations/
│   └── versions/
│       ├── add_certificates_table.py
│       └── add_venue_booking_tables.py
│
├── scripts/
│   ├── create_admin.py
│   └── init_db.py
│
├── config.py
├── requirements.txt
├── run.py
└── README.md
```

---

## 🚀 Installation

### 1. Clone the Repository

```bash
git clone https://github.com/Shubham5026v/Event-Manager.git
cd Event-Manager
```

### 2. Create a Virtual Environment

**Windows:**
```bash
python -m venv .venv
.venv\Scripts\activate
```

**macOS/Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

---

## ⚙️ Environment Setup

Create a `.env` file in the root directory:

```env
FLASK_APP=run.py
FLASK_ENV=development
SECRET_KEY=your-secret-key-here
DATABASE_URL=sqlite:///event_manager.db
```

> For production, use a strong secret key and a production-ready database.

---

## 🗄️ Database Setup

**Option 1 — Initialize using script:**
```bash
python scripts/init_db.py
```

**Option 2 — Use Flask Migrations:**
```bash
flask db upgrade
```

If migrations haven't been initialized yet:
```bash
flask db init
flask db migrate -m "Initial migration"
flask db upgrade
```

---

## 👤 Create Admin User

```bash
python scripts/create_admin.py
```

Then log in through the application's login page.

---

## ▶️ Run the Application

```bash
python run.py
```

Open in your browser:

```
http://127.0.0.1:5000
```

---

## 📦 Application Modules

### Admin Module
Provides control over event operations, team management, judge management, scoring, certificates, and venue approvals.

```
app/templates/admin/dashboard.html
app/templates/admin/events.html
app/templates/admin/scores.html
app/templates/admin/teams.html
```

### Authentication Module
Handles login, team registration, and judge registration.

```
app/templates/login.html
app/templates/auth/register_team.html
app/templates/auth/register_judge.html
```

### Booking Module
Handles venue booking creation, editing, viewing, status tracking, statistics, and user-specific booking lists.

```
app/templates/booking/create.html
app/templates/booking/edit.html
app/templates/booking/index.html
app/templates/booking/my_bookings.html
app/templates/booking/stats.html
app/templates/booking/view.html
```

### Venue Module
Handles venue availability, approval queue, approval history, booking calendar, and booking creation.

```
app/templates/venue/availability.html
app/templates/venue/approval_queue.html
app/templates/venue/approval_history.html
app/templates/venue/booking_calendar.html
app/templates/venue/booking_detail.html
app/templates/venue/create_booking.html
app/templates/venue/index.html
```

### Judge Module
Allows judges to access their dashboard and evaluation panel.

```
app/templates/judge/dashboard.html
app/templates/judge/panel.html
```

### Team Module
Allows teams to access dashboards and view certificates.

```
app/templates/team/dashboard.html
app/templates/team/certificates.html
```

### Certificate Module
Handles certificate generation, preview, public view, verification, and download.

```
app/templates/admin/certificates/generate.html
app/templates/admin/certificates/index.html
app/templates/admin/certificates/preview.html
app/templates/public/certificates/verify.html
app/templates/public/certificates/view.html
app/templates/public/certificates/download.html
```

---

## 🔧 Services Layer

Business logic is separated into dedicated service files:

| Service | Responsibility |
|---|---|
| `approval_service.py` | Handles approval workflows |
| `booking_service.py` | Manages booking logic |
| `calendar_service.py` | Calendar and availability operations |
| `certificate_generator.py` | Certificate creation |
| `notification_service.py` | Notification logic |
| `priority_service.py` | Priority-based booking decisions |
| `venue_service.py` | Venue-related operations |

---

## 🗂️ Important Files

| File | Purpose |
|---|---|
| `run.py` | Main application entry point |
| `config.py` | Application configuration |
| `requirements.txt` | Python dependencies |
| `app/models.py` | Database models |
| `app/forms.py` | Flask-WTF forms |
| `app/utils.py` | Utility/helper functions |
| `app/__init__.py` | Flask app initialization |

---

## 🙈 .gitignore

```gitignore
# Python cache
__pycache__/
*.pyc
*.pyo
*.pyd

# Virtual environments
.venv/
venv/
env/
app/venv/

# Environment variables
.env
.env.*
!.env.example

# Database files
instance/
*.db
*.sqlite
*.sqlite3
*.bak

# Local structure files
folder_structure.txt
structure.txt

# Logs
logs/
*.log

# OS files
.DS_Store
Thumbs.db
```

---

## 🔮 Future Improvements

- [ ] Email notifications for booking approval and rejection
- [ ] QR code verification for certificates
- [ ] Role-based access control decorators
- [ ] REST API endpoints for mobile or external integrations
- [ ] Dashboard analytics for admin users
- [ ] Docker support
- [ ] PostgreSQL support for production deployment
- [ ] Unit tests and integration tests
- [ ] CI/CD pipeline using GitHub Actions
- [ ] Deploy on Render, Railway, or PythonAnywhere

---

## 👨‍💻 Author

**Shubham**

GitHub: [Shubham5026v](https://github.com/Shubham5026v)

---

## 📄 License

This project is available for educational, portfolio, and development purposes.
