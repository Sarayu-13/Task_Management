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

## Intentional Issues (targets for modernisation)

### Backend – `app_manager.py`

| Anti-pattern | Description |
|---|---|
| **God Class** | `AppManager` handles DB init, auth, users, projects, tasks, comments, notifications, email, reporting, file storage, and search in one class |
| **Hardcoded secrets** | `SECRET_KEY = "supersecretkey123"` and `DB_PATH` are literals |
| **No layered architecture** | Zero separation between repository, service, and controller layers |
| **No dependency injection** | `AppManager` creates its own DB connection; impossible to swap |
| **Singleton export** | `app_manager = AppManager()` at module level |
| **Side-effects in data methods** | `update_task()` fires emails and notifications; `login_user()` queues emails |
| **Mixed concerns** | Schema creation, validation, business logic, and persistence in one method |
| **In-memory + DB split state** | `notifications_cache` and `active_users` dicts duplicate DB state |
| **Nested sequential DB calls** | Reports open 3 successive DB queries instead of a JOIN |
| **Risky optional import** | `import psutil` inside `get_system_stats()` with no graceful fallback |

### Backend – `app.py`

| Anti-pattern | Description |
|---|---|
| **Auth repeated on every route** | `_get_current_user()` copy-pasted instead of a middleware decorator |
| **Business logic in routes** | Role checks, branching by query param, cascade decisions live in route handlers |
| **No request validation** | Raw `data.get(...)` with no schema (Pydantic / Marshmallow) |
| **Inconsistent error handling** | Some routes catch `ValueError`, others return bare 500 |
| **Open CORS** | `CORS(app)` with no origin whitelist |

### Frontend – `App.js`

| Anti-pattern | Description |
|---|---|
| **God Component** | 700+ lines; all state, API calls, and rendering in one file |
| **No API layer** | Raw `fetch()` calls scattered in event handlers |
| **No custom hooks** | Auth, data-fetching, and form logic are all inline |
| **No component decomposition** | Login, register, kanban, task detail, report, search all render in one `return` |
| **Manual form state** | 25+ `useState` fields for forms instead of a form library |
| **Stale closure risk** | `loadDashboard` called with stale `token` captured in `useEffect` |
| **Token in localStorage** | No expiry check or secure storage strategy |
| **Magic strings** | `'todo'`, `'in_progress'`, `'done'`, `'blocked'` repeated throughout |

---

## Modernisation Ideas

- Split `AppManager` into `UserRepository`, `ProjectRepository`, `TaskRepository`,
  `NotificationService`, `EmailService`, `ReportService`
- Move secrets to `.env` / environment variables
- Add a proper auth middleware / decorator in Flask
- Add Pydantic models for request validation
- Replace the god component with a proper component tree:
  `<AuthProvider>` → `<Layout>` → `<ProjectList>` → `<TaskBoard>` → `<TaskCard>`
- Extract an `api.js` module (or React Query / SWR) for all HTTP calls
- Replace manual form state with React Hook Form
- Add `useAuth`, `useProjects`, `useTasks` custom hooks
- Add proper error boundaries
- Use an ORM (SQLAlchemy) instead of raw SQL
