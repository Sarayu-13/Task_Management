import sqlite3
import bcrypt
import jwt
import os
import json
import math
from datetime import datetime, timezone

SECRET_KEY = "supersecretkey123"
DB_PATH = os.path.join(os.path.dirname(__file__), "app.db")
TOKEN_EXPIRY_HOURS = 24


def _now():
    return datetime.now(timezone.utc).isoformat()


class AppManager:

    def __init__(self):
        self.db_path = DB_PATH
        self.notifications_cache = []
        self.email_queue = []
        self.report_cache = {}
        self.active_users = {}
        self.file_store = {}
        self._init_db()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_db(self):
        with self._get_conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    username    TEXT    UNIQUE NOT NULL,
                    email       TEXT    UNIQUE NOT NULL,
                    password    TEXT    NOT NULL,
                    role        TEXT    DEFAULT 'user',
                    bio         TEXT,
                    avatar      TEXT,
                    settings    TEXT    DEFAULT '{}',
                    last_login  TEXT,
                    created_at  TEXT    DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS projects (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    name        TEXT    NOT NULL,
                    description TEXT,
                    owner_id    INTEGER,
                    status      TEXT    DEFAULT 'active',
                    priority    TEXT    DEFAULT 'medium',
                    start_date  TEXT,
                    end_date    TEXT,
                    budget      REAL,
                    tags        TEXT,
                    created_at  TEXT    DEFAULT (datetime('now')),
                    updated_at  TEXT    DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS tasks (
                    id               INTEGER PRIMARY KEY AUTOINCREMENT,
                    title            TEXT    NOT NULL,
                    description      TEXT,
                    project_id       INTEGER,
                    assignee_id      INTEGER,
                    creator_id       INTEGER,
                    status           TEXT    DEFAULT 'todo',
                    priority         TEXT    DEFAULT 'medium',
                    due_date         TEXT,
                    estimated_hours  REAL,
                    actual_hours     REAL,
                    tags             TEXT,
                    attachments      TEXT    DEFAULT '[]',
                    created_at       TEXT    DEFAULT (datetime('now')),
                    updated_at       TEXT    DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS comments (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id    INTEGER,
                    user_id    INTEGER,
                    content    TEXT    NOT NULL,
                    created_at TEXT    DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS notifications (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id    INTEGER,
                    message    TEXT,
                    type       TEXT,
                    is_read    INTEGER DEFAULT 0,
                    created_at TEXT    DEFAULT (datetime('now'))
                );
            """)

    def register_user(self, username, email, password, role="user"):
        if not username or len(username) < 3:
            raise ValueError("Username must be at least 3 characters")
        if not email or "@" not in email:
            raise ValueError("Invalid email address")
        if not password or len(password) < 6:
            raise ValueError("Password must be at least 6 characters")

        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

        try:
            with self._get_conn() as conn:
                cur = conn.execute(
                    "INSERT INTO users (username, email, password, role) VALUES (?,?,?,?)",
                    (username, email, hashed, role),
                )
                return {"id": cur.lastrowid, "username": username, "email": email, "role": role}
        except sqlite3.IntegrityError:
            raise ValueError("Username or email already exists")

    def login_user(self, email, password):
        with self._get_conn() as conn:
            user = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()

        if not user:
            raise ValueError("User not found")

        if not bcrypt.checkpw(password.encode(), user["password"].encode()):
            raise ValueError("Invalid password")

        with self._get_conn() as conn:
            conn.execute("UPDATE users SET last_login=? WHERE id=?", (_now(), user["id"]))

        self.active_users[user["id"]] = {
            "id": user["id"],
            "username": user["username"],
            "login_time": _now(),
        }

        self.email_queue.append({
            "to": user["email"],
            "subject": "New login detected",
            "body": f"Hi {user['username']}, you logged in at {_now()}",
        })
        self._process_email_queue()

        token = jwt.encode(
            {
                "id": user["id"],
                "role": user["role"],
                "exp": datetime.now(timezone.utc).timestamp() + TOKEN_EXPIRY_HOURS * 3600,
            },
            SECRET_KEY,
            algorithm="HS256",
        )
        return {
            "token": token,
            "user": {
                "id": user["id"],
                "username": user["username"],
                "email": user["email"],
                "role": user["role"],
            },
        }

    def verify_token(self, token):
        try:
            return jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            raise ValueError("Token expired")
        except jwt.InvalidTokenError:
            raise ValueError("Invalid token")

    def get_user_by_id(self, user_id):
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT id, username, email, role, bio, avatar, created_at, last_login FROM users WHERE id=?",
                (user_id,),
            ).fetchone()
        if not row:
            raise ValueError("User not found")
        return dict(row)

    def get_all_users(self):
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT id, username, email, role, created_at, last_login FROM users"
            ).fetchall()
        return [dict(r) for r in rows]

    def update_user_profile(self, user_id, data):
        username = data.get("username")
        email = data.get("email")
        bio = data.get("bio")
        avatar = data.get("avatar")
        with self._get_conn() as conn:
            conn.execute(
                """UPDATE users SET
                     username = COALESCE(?, username),
                     email    = COALESCE(?, email),
                     bio      = COALESCE(?, bio),
                     avatar   = COALESCE(?, avatar)
                   WHERE id=?""",
                (username, email, bio, avatar, user_id),
            )
        return {"message": "Profile updated"}

    def delete_user(self, user_id):
        with self._get_conn() as conn:
            conn.execute("DELETE FROM users WHERE id=?", (user_id,))
        self.active_users.pop(user_id, None)
        return {"message": "User deleted"}

    def create_project(self, data, owner_id):
        name = data.get("name")
        if not name:
            raise ValueError("Project name is required")

        tags = data.get("tags", [])
        tags_str = ",".join(tags) if isinstance(tags, list) else (tags or "")

        with self._get_conn() as conn:
            cur = conn.execute(
                """INSERT INTO projects (name, description, owner_id, priority, start_date, end_date, budget, tags)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (
                    name,
                    data.get("description"),
                    owner_id,
                    data.get("priority", "medium"),
                    data.get("start_date"),
                    data.get("end_date"),
                    data.get("budget"),
                    tags_str,
                ),
            )
            return {"id": cur.lastrowid, "name": name, "owner_id": owner_id}

    def get_project_by_id(self, project_id):
        with self._get_conn() as conn:
            row = conn.execute(
                """SELECT p.*, u.username AS owner_name
                   FROM projects p
                   LEFT JOIN users u ON p.owner_id = u.id
                   WHERE p.id=?""",
                (project_id,),
            ).fetchone()
        if not row:
            raise ValueError("Project not found")
        return dict(row)

    def get_all_projects(self, owner_id=None):
        with self._get_conn() as conn:
            if owner_id:
                rows = conn.execute(
                    """SELECT p.*, u.username AS owner_name,
                              (SELECT COUNT(*) FROM tasks WHERE project_id=p.id) AS task_count,
                              (SELECT COUNT(*) FROM tasks WHERE project_id=p.id AND status='done') AS completed_tasks
                       FROM projects p
                       LEFT JOIN users u ON p.owner_id=u.id
                       WHERE p.owner_id=?""",
                    (owner_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT p.*, u.username AS owner_name,
                              (SELECT COUNT(*) FROM tasks WHERE project_id=p.id) AS task_count,
                              (SELECT COUNT(*) FROM tasks WHERE project_id=p.id AND status='done') AS completed_tasks
                       FROM projects p
                       LEFT JOIN users u ON p.owner_id=u.id"""
                ).fetchall()
        return [dict(r) for r in rows]

    def update_project(self, project_id, data):
        tags = data.get("tags")
        tags_str = ",".join(tags) if isinstance(tags, list) else tags
        with self._get_conn() as conn:
            conn.execute(
                """UPDATE projects SET
                     name        = COALESCE(?, name),
                     description = COALESCE(?, description),
                     status      = COALESCE(?, status),
                     priority    = COALESCE(?, priority),
                     start_date  = COALESCE(?, start_date),
                     end_date    = COALESCE(?, end_date),
                     budget      = COALESCE(?, budget),
                     tags        = COALESCE(?, tags),
                     updated_at  = ?
                   WHERE id=?""",
                (
                    data.get("name"),
                    data.get("description"),
                    data.get("status"),
                    data.get("priority"),
                    data.get("start_date"),
                    data.get("end_date"),
                    data.get("budget"),
                    tags_str,
                    _now(),
                    project_id,
                ),
            )
        return {"message": "Project updated"}

    def delete_project(self, project_id):
        with self._get_conn() as conn:
            conn.execute("DELETE FROM tasks WHERE project_id=?", (project_id,))
            conn.execute("DELETE FROM projects WHERE id=?", (project_id,))
        return {"message": "Project deleted"}

    def create_task(self, data, creator_id):
        title = data.get("title")
        if not title:
            raise ValueError("Task title is required")

        tags_str = (
            ",".join(data.get("tags", []))
            if isinstance(data.get("tags"), list)
            else (data.get("tags") or "")
        )

        with self._get_conn() as conn:
            cur = conn.execute(
                """INSERT INTO tasks
                     (title, description, project_id, assignee_id, creator_id,
                      priority, due_date, estimated_hours, tags)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    title,
                    data.get("description"),
                    data.get("project_id"),
                    data.get("assignee_id"),
                    creator_id,
                    data.get("priority", "medium"),
                    data.get("due_date"),
                    data.get("estimated_hours"),
                    tags_str,
                ),
            )
            task_id = cur.lastrowid

        if data.get("assignee_id"):
            self._add_notification(
                data["assignee_id"],
                f"You have been assigned to task: {title}",
                "task_assigned",
            )

        return {"id": task_id, "title": title, "creator_id": creator_id}

    def get_task_by_id(self, task_id):
        with self._get_conn() as conn:
            row = conn.execute(
                """SELECT t.*,
                          u1.username AS assignee_name,
                          u2.username AS creator_name,
                          p.name      AS project_name
                   FROM tasks t
                   LEFT JOIN users    u1 ON t.assignee_id = u1.id
                   LEFT JOIN users    u2 ON t.creator_id  = u2.id
                   LEFT JOIN projects p  ON t.project_id  = p.id
                   WHERE t.id=?""",
                (task_id,),
            ).fetchone()
        if not row:
            raise ValueError("Task not found")
        return dict(row)

    def get_tasks_by_project(self, project_id):
        with self._get_conn() as conn:
            rows = conn.execute(
                """SELECT t.*, u.username AS assignee_name
                   FROM tasks t
                   LEFT JOIN users u ON t.assignee_id = u.id
                   WHERE t.project_id=?
                   ORDER BY t.created_at DESC""",
                (project_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_tasks_by_assignee(self, user_id):
        with self._get_conn() as conn:
            rows = conn.execute(
                """SELECT t.*, p.name AS project_name
                   FROM tasks t
                   LEFT JOIN projects p ON t.project_id = p.id
                   WHERE t.assignee_id=?
                   ORDER BY t.due_date ASC""",
                (user_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def update_task(self, task_id, data):
        tags = data.get("tags")
        tags_str = ",".join(tags) if isinstance(tags, list) else tags

        with self._get_conn() as conn:
            conn.execute(
                """UPDATE tasks SET
                     title           = COALESCE(?, title),
                     description     = COALESCE(?, description),
                     status          = COALESCE(?, status),
                     priority        = COALESCE(?, priority),
                     due_date        = COALESCE(?, due_date),
                     estimated_hours = COALESCE(?, estimated_hours),
                     actual_hours    = COALESCE(?, actual_hours),
                     assignee_id     = COALESCE(?, assignee_id),
                     tags            = COALESCE(?, tags),
                     updated_at      = ?
                   WHERE id=?""",
                (
                    data.get("title"),
                    data.get("description"),
                    data.get("status"),
                    data.get("priority"),
                    data.get("due_date"),
                    data.get("estimated_hours"),
                    data.get("actual_hours"),
                    data.get("assignee_id"),
                    tags_str,
                    _now(),
                    task_id,
                ),
            )

        if data.get("status") == "done":
            self._add_notification(None, f"Task {task_id} completed", "task_completed")
            self.email_queue.append({
                "to": "team@company.com",
                "subject": f"Task {task_id} completed",
                "body": "A task has been marked as done.",
            })
            self._process_email_queue()

        return {"message": "Task updated"}

    def delete_task(self, task_id):
        with self._get_conn() as conn:
            conn.execute("DELETE FROM comments WHERE task_id=?", (task_id,))
            conn.execute("DELETE FROM tasks WHERE id=?", (task_id,))
        return {"message": "Task deleted"}

    def add_comment(self, task_id, user_id, content):
        if not content or not content.strip():
            raise ValueError("Comment cannot be empty")
        with self._get_conn() as conn:
            cur = conn.execute(
                "INSERT INTO comments (task_id, user_id, content) VALUES (?,?,?)",
                (task_id, user_id, content),
            )
            return {"id": cur.lastrowid, "task_id": task_id, "user_id": user_id, "content": content}

    def get_comments_by_task(self, task_id):
        with self._get_conn() as conn:
            rows = conn.execute(
                """SELECT c.*, u.username
                   FROM comments c
                   LEFT JOIN users u ON c.user_id = u.id
                   WHERE c.task_id=?
                   ORDER BY c.created_at ASC""",
                (task_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def delete_comment(self, comment_id):
        with self._get_conn() as conn:
            conn.execute("DELETE FROM comments WHERE id=?", (comment_id,))
        return {"message": "Comment deleted"}

    def _add_notification(self, user_id, message, notif_type):
        self.notifications_cache.append({
            "user_id": user_id,
            "message": message,
            "type": notif_type,
            "ts": _now(),
        })
        if user_id:
            with self._get_conn() as conn:
                conn.execute(
                    "INSERT INTO notifications (user_id, message, type) VALUES (?,?,?)",
                    (user_id, message, notif_type),
                )

    def get_notifications(self, user_id):
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM notifications WHERE user_id=? ORDER BY created_at DESC LIMIT 50",
                (user_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def mark_notification_read(self, notif_id):
        with self._get_conn() as conn:
            conn.execute("UPDATE notifications SET is_read=1 WHERE id=?", (notif_id,))
        return {"message": "Marked as read"}

    def _process_email_queue(self):
        while self.email_queue:
            email = self.email_queue.pop(0)
            print(f"[EMAIL] To: {email['to']} | Subject: {email['subject']}")

    def send_password_reset(self, email):
        import random
        import string
        token = "".join(random.choices(string.ascii_letters + string.digits, k=16))
        self.email_queue.append({
            "to": email,
            "subject": "Password Reset Request",
            "body": f"Your reset token: {token}",
        })
        self._process_email_queue()
        return {"message": "Reset email sent", "debug_token": token}

    def generate_project_report(self, project_id):
        with self._get_conn() as conn:
            project = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
            if not project:
                raise ValueError("Project not found")
            tasks = conn.execute("SELECT * FROM tasks WHERE project_id=?", (project_id,)).fetchall()

        tasks = [dict(t) for t in tasks]
        total = len(tasks)
        done = sum(1 for t in tasks if t["status"] == "done")
        in_progress = sum(1 for t in tasks if t["status"] == "in_progress")
        todo = sum(1 for t in tasks if t["status"] == "todo")
        now = datetime.now(timezone.utc)
        overdue = sum(
            1 for t in tasks
            if t["due_date"]
            and datetime.fromisoformat(t["due_date"]).replace(tzinfo=timezone.utc) < now
            and t["status"] != "done"
        )

        report = {
            "project": dict(project),
            "total_tasks": total,
            "completed_tasks": done,
            "in_progress_tasks": in_progress,
            "todo_tasks": todo,
            "overdue_tasks": overdue,
            "total_estimated_hours": sum(t.get("estimated_hours") or 0 for t in tasks),
            "total_actual_hours": sum(t.get("actual_hours") or 0 for t in tasks),
            "completion_rate": round((done / total) * 100) if total else 0,
            "generated_at": _now(),
        }

        self.report_cache[f"project_{project_id}"] = {"data": report, "ts": _now()}
        return report

    def generate_user_report(self, user_id):
        with self._get_conn() as conn:
            user = conn.execute(
                "SELECT id, username, email FROM users WHERE id=?", (user_id,)
            ).fetchone()
            tasks = conn.execute(
                "SELECT * FROM tasks WHERE assignee_id=?", (user_id,)
            ).fetchall()
            projects = conn.execute(
                "SELECT * FROM projects WHERE owner_id=?", (user_id,)
            ).fetchall()

        tasks = [dict(t) for t in tasks]
        total = len(tasks)
        done = sum(1 for t in tasks if t["status"] == "done")
        now = datetime.now(timezone.utc)
        overdue = sum(
            1 for t in tasks
            if t["due_date"]
            and datetime.fromisoformat(t["due_date"]).replace(tzinfo=timezone.utc) < now
            and t["status"] != "done"
        )
        return {
            "user": dict(user),
            "assigned_tasks": total,
            "completed_tasks": done,
            "overdue_tasks": overdue,
            "owned_projects": len(projects),
            "productivity_pct": round((done / total) * 100) if total else 0,
            "generated_at": _now(),
        }

    def get_system_stats(self):
        import psutil
        with self._get_conn() as conn:
            user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            project_count = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
            task_count = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
            comment_count = conn.execute("SELECT COUNT(*) FROM comments").fetchone()[0]
        return {
            "total_users": user_count,
            "total_projects": project_count,
            "total_tasks": task_count,
            "total_comments": comment_count,
            "active_users": len(self.active_users),
            "notification_cache_size": len(self.notifications_cache),
            "email_queue_size": len(self.email_queue),
            "report_cache_entries": len(self.report_cache),
        }

    def attach_file_to_task(self, task_id, file_name, file_data):
        self.file_store[f"task_{task_id}_{file_name}"] = file_data

        with self._get_conn() as conn:
            row = conn.execute("SELECT attachments FROM tasks WHERE id=?", (task_id,)).fetchone()
            attachments = json.loads(row["attachments"] or "[]") if row else []
            attachments.append({"name": file_name, "uploaded_at": _now()})
            conn.execute(
                "UPDATE tasks SET attachments=? WHERE id=?",
                (json.dumps(attachments), task_id),
            )
        return {"message": "File attached", "attachments": attachments}

    def search(self, query):
        q = f"%{query}%"
        with self._get_conn() as conn:
            tasks = conn.execute(
                "SELECT id, title AS name, 'task' AS type FROM tasks WHERE title LIKE ? OR description LIKE ?",
                (q, q),
            ).fetchall()
            projects = conn.execute(
                "SELECT id, name, 'project' AS type FROM projects WHERE name LIKE ? OR description LIKE ?",
                (q, q),
            ).fetchall()
        return {
            "tasks": [dict(r) for r in tasks],
            "projects": [dict(r) for r in projects],
            "total": len(tasks) + len(projects),
        }

    def get_user_settings(self, user_id):
        with self._get_conn() as conn:
            row = conn.execute("SELECT settings FROM users WHERE id=?", (user_id,)).fetchone()
        return json.loads(row["settings"] or "{}") if row else {}

    def update_user_settings(self, user_id, settings_dict):
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE users SET settings=? WHERE id=?",
                (json.dumps(settings_dict), user_id),
            )
        return {"message": "Settings saved"}

    def _calculate_pages(self, total, per_page):
        return math.ceil(total / per_page) if per_page else 0


app_manager = AppManager()
