# SEA-1 MCQ Battle Platform

A competitive, highly interactive full-stack Multiple Choice Question (MCQ) practice arena where students can test their computer science knowledge, maintain practice streaks, earn XP awards, unlock rank badges, and compete on dynamic standing leaderboards. 

This platform is structured with modern security protocols, stateless JWT session tokens, and dynamic data auditing dashboards, making it suitable for final-year project presentations.

---

## 🚀 Key Features

* **Authentication System**: Secure registration and login flows powered by stateless JWT Bearer authorization tokens and password hashing via `werkzeug.security`.
* **Dynamic Quiz Arena**: 10 randomized MCQs with category filters and difficulty configurations. Includes a ticking 5-minute global countdown timer, responsive question navigation bubbles, progress indicators, and backend-enforced secure grading (preventing inspecting code to cheat).
* **Gamified Progression (Streaks & XP)**:
  * Persistent daily practice streaks: rewards consecutive logins and resets if days are missed.
  * XP Reward system: base points per correct answer + streak modifiers + 100% accuracy modifiers.
  * Rank Badge updates: Automatic promotions across Bronze, Silver, Gold, and Platinum ranks based on accrued XP.
* **Interactive Dashboards**: Powered by **Chart.js** to render performance trends across student history. Includes history attempt logs and highscore cards.
* **Global Standings Leaderboards**: Real-time ranking with toggle scopes for *Today*, *Weekly*, and *All-Time*. Gold, Silver, and Bronze medal visual podiums for the top 3 spots!
* **Comprehensive Admin Center**: Complete Question Bank Builder (CRUD) allowing question addition, modification, and deletion. Includes a pastable JSON Bulk Importer and User DB logs auditing.

---

## 🛠️ Technology Stack

### Frontend:
* **HTML5 & CSS3**: Core structures, custom animations, custom scrollbars, gold/silver/bronze podium frames.
* **Vanilla JavaScript (ES6)**: State manager, JWT controllers, fetch wrappers, navbar loaders, and timer clocks.
* **Tailwind CSS CDN**: Backdrop-blur filters, grid layouts, radial mesh glows, and glassmorphic designs.
* **Chart.js CDN**: Smooth animated performance progression charts.
* **Font Awesome Icons**: Visual icons library.

### Backend:
* **Python Flask**: Application factory structures and router controllers.
* **Flask-SQLAlchemy ORM**: Database object-relational mapping.
* **Flask-JWT-Extended**: Stateless authentication and protected route management.
* **Flask-CORS**: Secure Cross-Origin Resource Sharing.

### Database:
* **MySQL (AWS RDS Production) / SQLite (Local Dev)**: MySQL on AWS RDS (Relational Database Service) powers the production database layer for high availability and isolation. SQLite acts as a zero-configuration out-of-the-box local fallback database.

---

## 📂 Project Structure

```text
c:\Desktop\mcq-portal\
│   requirements.txt
│   README.md
│   run.py
│   .env
│   .env.example
│
├───backend
│   │   app.py
│   │   config.py
│   │   models.py
│   │   __init__.py
│   │
│   ├───blueprints
│   │       auth.py
│   │       quiz.py
│   │       admin.py
│   │       stats.py
│   │       __init__.py
│   │
│   └───utils
│           __init__.py
│           helpers.py
│
└───frontend
    │   index.html
    │   login.html
    │   register.html
    │   dashboard.html
    │   quiz.html
    │   leaderboard.html
    │   results.html
    │   admin.html
    │   profile.html
    │   style.css
    │   app.js
```

---

## 📝 Database Schema

The database relies on four primary tables managed through Flask-SQLAlchemy:

1. **`users`**: Manages credentials, current streak count, XP tallies, and rank badges.
2. **`mcqs`**: Question pool comprising prompt texts, choice pairs A/B/C/D, correct indicators, categories, and difficulty metrics.
3. **`attempts`**: History records containing quiz scores, question counts, and correctness percentages for each attempt.
4. **`stats`**: Aggregate student metadata (highest score, average score, consistency accuracy ratio, and total attempts count).

---

## ⚙️ Local Setup Instructions

Ensure you have **Python 3.8 or higher** installed on your system.

### 1. Clone or Move to Workspace
Open your terminal inside the project directory:
```bash
cd c:\Desktop\mcq-portal
```

### 2. Configure Virtual Environment (Recommended)
Create and activate a Python virtual environment:
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
Run pip install to fetch backend packages (Flask, SQLAlchemy, JWT, CORS, pymysql, etc.):
```bash
pip install -r requirements.txt
```

### 4. Database Setup & Configurations
The portal is set up to automatically create and seed 10 default, high-quality computer science questions into a local database on startup.

* **SQLite Default (Out-of-the-box)**: 
  No setup required. The `.env` file automatically fallbacks to `sqlite:///mcq_battle.db` in your workspace.
* **MySQL (AWS RDS) Configuration**:
  To connect to your production MySQL database on AWS RDS, configure your credentials inside your `.env` file:
  ```env
  DATABASE_URL=mysql+pymysql://username:password@rds-endpoint:3306/mcq_battle
  ```

### 5. Start the Application
Launch the Flask development server:
```bash
python run.py
```

Open your web browser and access the platform at:
👉 **[http://localhost:5000](http://localhost:5000)**

---

## 🛡️ Security Features Implemented

* **Stateless Token Authentication**: Authentication endpoints sign JWT Bearer tokens. Standard security filters reject unauthorized clients.
* **Password Hashing**: Student passwords are saved in the database as salted hashes via SHA256 (through `werkzeug.security`), preventing plain-text exposures.
* **Anti-Cheat Grading Engine**: Question lists serve to clients without the `correct_answer` fields, preventing students from inspecting the network panel to find correct answers. Grading calculations happen completely on the secure server side.
* **SQL Injection & XSS Shielding**: Inputs sanitize through the SQLAlchemy ORM query structures, shielding database engines from arbitrary malicious payloads.
