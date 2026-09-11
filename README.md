# 🎓 AI Study Planner Web Application

A smart, modern, and easy-to-use academic study management web app built with **Python (Flask)**, **SQLite**, **Bootstrap 5**, and **Chart.js**.

It helps college students manage their daily studies, organize subjects, track pending tasks, and get **intelligent AI-based study recommendations** based on approaching deadlines and syllabus completion.

---

## 🌟 What Problem Does This App Solve?

Students often struggle with:
* *"Which subject should I study first?"*
* *"How do I track my exam deadlines without panic?"*
* *"How can I maintain a daily study habit?"*

This app acts as your **Personal Academic Assistant**:
1. **Prioritizes Urgent Deadlines:** Flags overdue and upcoming tasks so you never miss an assignment.
2. **Detects Weak Subjects:** Suggests which subject needs more attention if syllabus progress is low.
3. **Builds Focus Schedules:** Automatically creates 50-minute Pomodoro study sessions with 10-minute breaks.
4. **Tracks Daily Habit Streaks 🔥:** Keeps you motivated by counting consecutive active study days.
5. **Visual Progress Charts:** Interactive graphs showing weekly hours and syllabus coverage.

---

## 🚀 Key Features

* **🔐 Modern Authentication & Security:**
  * Clean, responsive Sign In and Sign Up pages with soft ambient glow backgrounds.
  * Password visibility eye toggle button (show/hide password).
  * Encrypted password hashing (Werkzeug) & private user data isolation.

* **📚 Task & Subject Manager:**
  * Add, view, filter, and delete college subjects.
  * Create tasks with priority tags (High 🔥, Medium ⚡, Low ☕) and deadlines.
  * Interactive checkbox to mark tasks as completed in one click.

* **🤖 Rule-Based AI Engine:**
  * **Urgency & Deficit Index (UDI):** Heuristic mathematical scoring that automatically recommends what to study next.
  * **Automated Daily Timetable:** Generates dynamic 50/10 focus-break blocks tailored to your daily study goal.
  * **Smart Insights:** Context-aware productivity tips based on your study habits.

* **📊 Interactive Analytics (Chart.js):**
  * Weekly study hours vs daily target.
  * Syllabus completion percentage per subject.
  * Task breakdown doughnut chart (Completed, In Progress, Pending, Overdue).
  * 30-day study consistency trend line.

* **⚙️ Profile & Habit Tracking:**
  * Editable student profile with daily target study hours.
  * Real-time study streak counter (🔥 Days).
  * 1-click Light and Dark mode switcher.

---

## 🛠️ Tech Stack Used

| Layer | Technologies |
|---|---|
| **Backend** | Python 3, Flask, Flask-SQLAlchemy, Flask-Login, Flask-WTF |
| **Database** | SQLite3 |
| **Frontend** | HTML5, CSS3, JavaScript, Bootstrap 5, Bootstrap Icons |
| **Visualizations** | Chart.js |

---

## 📁 Project Structure

\\\	ext
ai_study_planner/
├── app.py                     # Main Flask routes & server controller
├── models.py                  # Database tables (Users, Subjects, Tasks, Progress)
├── forms.py                   # Form validation & security
├── requirements.txt           # Python library dependencies
├── database.db                # SQLite database (auto-generated)
│
├── utils/
│   ├── __init__.py
│   └── recommendation_engine.py  # Rule-based AI decision logic
│
├── static/
│   ├── css/style.css          # Custom styling & dark mode rules
│   └── js/main.js             # Chart.js initializers & checkbox toggles
│
└── templates/                 # Frontend HTML pages
    ├── base.html              # Base layout with sidebar & streak badge
    ├── index.html             # Landing showcase page
    ├── login.html             # Modern Sign In page with eye toggle
    ├── register.html          # Sign Up page with validation
    ├── dashboard.html         # Main student dashboard & Pomodoro timetable
    ├── planner.html           # Task & subject manager
    ├── reports.html           # Analytics & visual charts
    └── profile.html           # Profile settings & daily goal adjuster
\\\

---

## ⚡ How to Run Locally

### 1. Clone the Repository
\\\ash
git clone https://github.com/<your-username>/ai-study-planner.git
cd ai-study-planner
\\\

### 2. Set Up Virtual Environment
\\\ash
# On Windows:
python -m venv venv
.\venv\Scripts\activate

# On Mac/Linux:
python3 -m venv venv
source venv/bin/activate
\\\

### 3. Install Dependencies
\\\ash
pip install -r requirements.txt
\\\

### 4. Run the Application
\\\ash
python app.py
\\\

### 5. Open in Your Browser
Visit:
\\\	ext
http://127.0.0.1:5000/
\\\

---

## 💡 How the Rule-Based AI Engine Works (Viva / Interview Explanation)

Instead of complex black-box machine learning, this application utilizes **Heuristic Decision Models**:

1. **Deadline Proximity Scoring:**
   Overdue tasks get maximum critical priority (100+). Tasks due today or tomorrow receive boosted urgency weights (90 and 80), amplified by priority factors (High = +30, Medium = +15).

2. **Urgency & Deficit Index (UDI):**
   }UDI = (Deficit \times 45) + (Urgency \times 0.55)}
   Subjects with the lowest syllabus completion and the most upcoming deadlines are dynamically pushed to the top of the recommendation queue.

3. **Pomodoro Time-Block Generation:**
   Divides the user's daily study target into 50-minute study sessions with 10-minute rest buffers, assigning highest-priority tasks into peak focus slots.

---

## 👨‍💻 Author

Built with ❤️ by **Vishu Singh** as an Academic / Portfolio Project.
