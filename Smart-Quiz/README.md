# Smart Quiz — Online Quiz Application

A professional, full-stack quiz web application built with **Flask + SQLite** frontend served with **Bootstrap 5**.

## Features

- User registration & login (secure password hashing via Werkzeug)
- 9 quiz categories × 20 questions each (180 MCQs)
- Interactive quiz interface: question navigation, progress bar, countdown timer
- Automatic score calculation, result storage, answer review
- Quiz history & performance tracking
- Dark / light mode toggle
- Admin panel: manage questions, categories, users, and view all results
- Fully responsive design with smooth animations

## Tech Stack

- **Backend:** Python, Flask
- **Database:** SQLite (swap to MySQL by changing the connection in `app.py`)
- **Frontend:** HTML5, CSS3, JavaScript, Bootstrap 5

## Installation

1. **Install Python 3.9+** from [python.org](https://python.org)

2. **Clone / extract this project folder**

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the application:**
   ```bash
   python app.py
   ```
   The database (`quiz.db`) and seed data (admin account + 180 questions) are created automatically on first run.

5. **Open in browser:**
   - Website: http://localhost:5000
   - Admin panel: http://localhost:5000/admin/login

## Default Credentials

| Role  | Username | Password  |
|-------|----------|-----------|
| Admin | `admin`  | `admin123`|

> Change the admin password after first login for security.

## Project Structure

```
jitu project/
├── app.py               # Flask backend (routes, auth, quiz API, admin)
├── seed_data.py         # Categories & 180 quiz questions
├── requirements.txt
├── quiz.db              # SQLite database (auto-created)
├── templates/
│   ├── base.html        # Main layout (navbar, theme toggle)
│   ├── index.html       # Landing page
│   ├── login.html / register.html
│   ├── dashboard.html   # User dashboard with categories & stats
│   ├── quiz.html        # Quiz interface
│   ├── result.html      # Score + answer review
│   ├── history.html     # Attempt history
│   ├── admin_base.html  # Admin layout
│   ├── admin_login.html
│   ├── admin_dashboard.html
│   ├── admin_questions.html / admin_question_form.html
│   ├── admin_categories.html
│   ├── admin_users.html
│   └── admin_results.html
└── static/
    ├── css/style.css    # Custom styles, animations, dark mode
    └── js/quiz.js       # Quiz engine (timer, navigation, submit)
```

## API Endpoints

| Method | Endpoint                  | Description                        |
|--------|---------------------------|------------------------------------|
| GET    | `/api/quiz/<cat_id>`      | Fetch questions (no answers)       |
| POST   | `/api/submit`             | Submit answers, returns result_id  |

## Notes

- Timer: 30 seconds per question (configurable via `TIME_PER_QUESTION` in `app.py`).
- To use MySQL, install `mysql-connector-python`, update `get_db()` in `app.py`, and run the schema in `init_db()`.
