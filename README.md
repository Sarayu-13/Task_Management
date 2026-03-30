# Task Manager – Modernisation Test Project

A full-stack Task & Project Management app built with intentional architectural
anti-patterns, so you can practise modernisation / refactoring.

---

## Stack

| Layer    | Technology              |
|----------|-------------------------|
| Backend  | Python 3.10+ · Flask    |
| Database | SQLite (file: app.db)   |
| Frontend | React 18 (CRA)          |

---

## Quick Start

### 1 – Backend

```bash
cd backend
pip install -r requirements.txt
python app.py
# Runs on http://localhost:5000
```

### 2 – Frontend (new terminal)

```bash
cd frontend
npm install
npm start
# Opens http://localhost:3000
```

### 3 – First steps in the UI

1. Click **Register** and create an account (use role `admin` to see all users).
2. Log in → you land on the **Dashboard**.
3. Create a **Project** → open it → add **Tasks**.
4. Drag tasks between Kanban columns (▶ / ✓ quick actions).
5. Click a task title to open the detail panel and add **comments**.
6. Use the **Report** button on any project to see analytics.
7. Use **Search** to find tasks / projects.

---

