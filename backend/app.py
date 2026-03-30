"""
Flask entry point.

Architecture issues present for modernisation:
  - Route handlers contain business logic (no controller / service split)
  - Auth middleware is a helper function copy-pasted on every route
  - Error handling is inconsistent – some routes return 500 bare, others 400
  - No request validation layer (Pydantic / Marshmallow)
  - God class (app_manager) called directly from routes
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
from app_manager import app_manager

app = Flask(__name__)
CORS(app)   # CORS open for all origins – security issue


# ------------------------------------------------------------------ #
#  Auth helper – should be middleware / decorator, not repeated code  #
# ------------------------------------------------------------------ #
def _get_current_user():
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token = auth.split(" ", 1)[1]
    try:
        return app_manager.verify_token(token)
    except Exception:
        return None


# ------------------------------------------------------------------ #
#  AUTH ROUTES                                                        #
# ------------------------------------------------------------------ #
@app.route("/api/auth/register", methods=["POST"])
def register():
    data = request.get_json() or {}
    try:
        user = app_manager.register_user(
            data.get("username"),
            data.get("email"),
            data.get("password"),
            data.get("role", "user"),
        )
        return jsonify(user), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception:
        return jsonify({"error": "Internal server error"}), 500


@app.route("/api/auth/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    try:
        result = app_manager.login_user(data.get("email"), data.get("password"))
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 401
    except Exception:
        return jsonify({"error": "Internal server error"}), 500


@app.route("/api/auth/reset-password", methods=["POST"])
def reset_password():
    data = request.get_json() or {}
    result = app_manager.send_password_reset(data.get("email"))
    return jsonify(result)


# ------------------------------------------------------------------ #
#  USER ROUTES                                                        #
# ------------------------------------------------------------------ #
@app.route("/api/users", methods=["GET"])
def get_users():
    # Auth check copy-pasted instead of using a decorator
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    # Role check mixed into route handler
    if user.get("role") != "admin":
        return jsonify({"error": "Forbidden"}), 403
    users = app_manager.get_all_users()
    return jsonify(users)


@app.route("/api/users/<int:user_id>", methods=["GET"])
def get_user(user_id):
    current = _get_current_user()
    if not current:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        return jsonify(app_manager.get_user_by_id(user_id))
    except ValueError as e:
        return jsonify({"error": str(e)}), 404


@app.route("/api/users/<int:user_id>", methods=["PUT"])
def update_user(user_id):
    current = _get_current_user()
    if not current:
        return jsonify({"error": "Unauthorized"}), 401
    # Business rule mixed in route: only self or admin can update
    if current["id"] != user_id and current.get("role") != "admin":
        return jsonify({"error": "Forbidden"}), 403
    data = request.get_json() or {}
    result = app_manager.update_user_profile(user_id, data)
    return jsonify(result)


@app.route("/api/users/<int:user_id>", methods=["DELETE"])
def delete_user(user_id):
    current = _get_current_user()
    if not current:
        return jsonify({"error": "Unauthorized"}), 401
    if current.get("role") != "admin":
        return jsonify({"error": "Forbidden"}), 403
    result = app_manager.delete_user(user_id)
    return jsonify(result)


@app.route("/api/users/<int:user_id>/settings", methods=["GET"])
def get_settings(user_id):
    current = _get_current_user()
    if not current:
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify(app_manager.get_user_settings(user_id))


@app.route("/api/users/<int:user_id>/settings", methods=["PUT"])
def update_settings(user_id):
    current = _get_current_user()
    if not current:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json() or {}
    return jsonify(app_manager.update_user_settings(user_id, data))


@app.route("/api/users/<int:user_id>/report", methods=["GET"])
def user_report(user_id):
    current = _get_current_user()
    if not current:
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify(app_manager.generate_user_report(user_id))


# ------------------------------------------------------------------ #
#  PROJECT ROUTES                                                     #
# ------------------------------------------------------------------ #
@app.route("/api/projects", methods=["GET"])
def get_projects():
    current = _get_current_user()
    if not current:
        return jsonify({"error": "Unauthorized"}), 401
    owner_id = request.args.get("owner_id", type=int)
    return jsonify(app_manager.get_all_projects(owner_id))


@app.route("/api/projects", methods=["POST"])
def create_project():
    current = _get_current_user()
    if not current:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json() or {}
    try:
        project = app_manager.create_project(data, current["id"])
        return jsonify(project), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/projects/<int:project_id>", methods=["GET"])
def get_project(project_id):
    current = _get_current_user()
    if not current:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        return jsonify(app_manager.get_project_by_id(project_id))
    except ValueError as e:
        return jsonify({"error": str(e)}), 404


@app.route("/api/projects/<int:project_id>", methods=["PUT"])
def update_project(project_id):
    current = _get_current_user()
    if not current:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json() or {}
    return jsonify(app_manager.update_project(project_id, data))


@app.route("/api/projects/<int:project_id>", methods=["DELETE"])
def delete_project(project_id):
    current = _get_current_user()
    if not current:
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify(app_manager.delete_project(project_id))


@app.route("/api/projects/<int:project_id>/report", methods=["GET"])
def project_report(project_id):
    current = _get_current_user()
    if not current:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        return jsonify(app_manager.generate_project_report(project_id))
    except ValueError as e:
        return jsonify({"error": str(e)}), 404


# ------------------------------------------------------------------ #
#  TASK ROUTES                                                        #
# ------------------------------------------------------------------ #
@app.route("/api/tasks", methods=["GET"])
def get_tasks():
    current = _get_current_user()
    if not current:
        return jsonify({"error": "Unauthorized"}), 401
    project_id = request.args.get("project_id", type=int)
    assignee_id = request.args.get("assignee_id", type=int)

    # Business logic branching mixed in route
    if project_id:
        return jsonify(app_manager.get_tasks_by_project(project_id))
    elif assignee_id:
        return jsonify(app_manager.get_tasks_by_assignee(assignee_id))
    else:
        return jsonify({"error": "Provide project_id or assignee_id"}), 400


@app.route("/api/tasks", methods=["POST"])
def create_task():
    current = _get_current_user()
    if not current:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json() or {}
    try:
        task = app_manager.create_task(data, current["id"])
        return jsonify(task), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/tasks/<int:task_id>", methods=["GET"])
def get_task(task_id):
    current = _get_current_user()
    if not current:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        return jsonify(app_manager.get_task_by_id(task_id))
    except ValueError as e:
        return jsonify({"error": str(e)}), 404


@app.route("/api/tasks/<int:task_id>", methods=["PUT"])
def update_task(task_id):
    current = _get_current_user()
    if not current:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json() or {}
    return jsonify(app_manager.update_task(task_id, data))


@app.route("/api/tasks/<int:task_id>", methods=["DELETE"])
def delete_task(task_id):
    current = _get_current_user()
    if not current:
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify(app_manager.delete_task(task_id))


@app.route("/api/tasks/<int:task_id>/attach", methods=["POST"])
def attach_file(task_id):
    current = _get_current_user()
    if not current:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json() or {}
    result = app_manager.attach_file_to_task(
        task_id, data.get("file_name", "file"), data.get("content", "")
    )
    return jsonify(result)


# ------------------------------------------------------------------ #
#  COMMENT ROUTES                                                     #
# ------------------------------------------------------------------ #
@app.route("/api/tasks/<int:task_id>/comments", methods=["GET"])
def get_comments(task_id):
    current = _get_current_user()
    if not current:
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify(app_manager.get_comments_by_task(task_id))


@app.route("/api/tasks/<int:task_id>/comments", methods=["POST"])
def add_comment(task_id):
    current = _get_current_user()
    if not current:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json() or {}
    try:
        comment = app_manager.add_comment(task_id, current["id"], data.get("content", ""))
        return jsonify(comment), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/comments/<int:comment_id>", methods=["DELETE"])
def delete_comment(comment_id):
    current = _get_current_user()
    if not current:
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify(app_manager.delete_comment(comment_id))


# ------------------------------------------------------------------ #
#  NOTIFICATION ROUTES                                                #
# ------------------------------------------------------------------ #
@app.route("/api/notifications", methods=["GET"])
def get_notifications():
    current = _get_current_user()
    if not current:
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify(app_manager.get_notifications(current["id"]))


@app.route("/api/notifications/<int:notif_id>/read", methods=["PUT"])
def mark_read(notif_id):
    current = _get_current_user()
    if not current:
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify(app_manager.mark_notification_read(notif_id))


# ------------------------------------------------------------------ #
#  SEARCH                                                             #
# ------------------------------------------------------------------ #
@app.route("/api/search", methods=["GET"])
def search():
    current = _get_current_user()
    if not current:
        return jsonify({"error": "Unauthorized"}), 401
    query = request.args.get("q", "")
    if not query:
        return jsonify({"error": "Query required"}), 400
    return jsonify(app_manager.search(query))


# ------------------------------------------------------------------ #
#  SYSTEM STATS                                                       #
# ------------------------------------------------------------------ #
@app.route("/api/stats", methods=["GET"])
def stats():
    current = _get_current_user()
    if not current:
        return jsonify({"error": "Unauthorized"}), 401
    if current.get("role") != "admin":
        return jsonify({"error": "Forbidden"}), 403
    try:
        return jsonify(app_manager.get_system_stats())
    except Exception:
        # psutil may not be installed – silent fallback
        return jsonify({"error": "Stats unavailable"}), 500


if __name__ == "__main__":
    app.run(debug=True, port=5000)
