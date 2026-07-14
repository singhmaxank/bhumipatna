import csv
import io
import os
<<<<<<< HEAD
import time

=======
>>>>>>> 0610f2665c1dc97c9fa417fa1c25fff8cef7d841
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
from functools import wraps

from flask import (Flask, flash, g, redirect, render_template, request,
                    session, url_for, Response)
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("BHUMI_SECRET_KEY", "dev-secret-key-change-in-production")

# How long a verified "forgot password" session is allowed to set a new password.
RESET_WINDOW_SECONDS = 10 * 60

# Rank tiers: (label, floor amount, ceiling amount or None for top tier)
RANK_TIERS = [
    ("Bronze", 0, 5000),
    ("Silver", 5000, 15000),
    ("Gold", 15000, 50000),
    ("Platinum", 50000, None),
]

MANAGEABLE_ROLES = ("intern", "ambassador")


# --------------------------------------------------------------------------
# Database helpers
# --------------------------------------------------------------------------
def get_db():
    if "db" not in g:
        g.db = psycopg2.connect(
<<<<<<< HEAD
            os.environ.get("DATABASE_URL"),
            cursor_factory=RealDictCursor,
=======
            os.environ.get('DATABASE_URL'),
            cursor_factory=RealDictCursor
>>>>>>> 0610f2665c1dc97c9fa417fa1c25fff8cef7d841
        )
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def query_db(query, args=(), one=False):
    db = get_db()
    cur = db.cursor()
    cur.execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv


def execute_db(query, args=()):
    db = get_db()
    cur = db.cursor()
    cur.execute(query, args)
    db.commit()
    cur.close()
    return None


# --------------------------------------------------------------------------
# Auth helpers
# --------------------------------------------------------------------------
def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def role_required(*roles):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if "user_id" not in session:
                return redirect(url_for("login"))
            if session.get("role") not in roles:
                flash("You do not have permission to view that page.", "error")
<<<<<<< HEAD
=======
                # Fix: Route users to their correct respective homepages
>>>>>>> 0610f2665c1dc97c9fa417fa1c25fff8cef7d841
                if session.get("role") == "admin":
                    return redirect(url_for("admin_panel"))
                return redirect(url_for("dashboard"))
            return view(*args, **kwargs)
        return wrapped
    return decorator


def current_user():
    if "user_id" not in session:
        return None
    return query_db("SELECT * FROM users WHERE id = %s", (session["user_id"],), one=True)


def get_rank(amount):
    """Returns (rank_label, current_amount, next_floor_amount_or_None, progress_pct)."""
    for label, floor, ceiling in RANK_TIERS:
        if ceiling is None or amount < ceiling:
            if ceiling is None:
                return label, amount, None, 100.0
            span = ceiling - floor
            progress = max(0.0, min(100.0, ((amount - floor) / span) * 100)) if span else 100.0
            return label, amount, ceiling, progress
    return RANK_TIERS[-1][0], amount, None, 100.0


def verified_total(user_id):
    row = query_db(
        "SELECT COALESCE(SUM(amount), 0) AS total FROM donations WHERE user_id = %s AND status = 'approved'",
        (user_id,), one=True,
    )
    return row["total"]


def org_leaderboard(limit=None):
    query = """SELECT u.id, u.full_name, u.role, COALESCE(SUM(d.amount), 0) AS total
               FROM users u
               LEFT JOIN donations d ON d.user_id = u.id AND d.status = 'approved'
               WHERE u.role IN ('intern', 'ambassador')
               GROUP BY u.id
               ORDER BY total DESC"""
    if limit:
        query += " LIMIT %s"
        return query_db(query, (limit,))
    return query_db(query)


# --------------------------------------------------------------------------
# Auth routes
# --------------------------------------------------------------------------
@app.route("/")
def index():
    if "user_id" in session:
<<<<<<< HEAD
=======
        # Fix: Direct admins to the admin panel, everyone else to dashboard
>>>>>>> 0610f2665c1dc97c9fa417fa1c25fff8cef7d841
        if session.get("role") == "admin":
            return redirect(url_for("admin_panel"))
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = query_db("SELECT * FROM users WHERE username = %s", (username,), one=True)

        if user is None or not check_password_hash(user["password_hash"], password):
            flash("Invalid username or password.", "error")
            return render_template("login.html")

        session.clear()
        session["user_id"] = user["id"]
        session["role"] = user["role"]
        session["full_name"] = user["full_name"]
        flash(f"Welcome back, {user['full_name']}!", "success")

        if user["role"] == "admin":
            return redirect(url_for("admin_panel"))
        return redirect(url_for("dashboard"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("login"))


# --------------------------------------------------------------------------
# Forgot / reset password
# --------------------------------------------------------------------------
@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()

        user = query_db(
            "SELECT * FROM users WHERE username = %s AND lower(email) = %s",
            (username, email), one=True,
        )

        if user is None:
            flash("We couldn't match that username and email. Please check and try again, or contact your admin.", "error")
            return render_template("forgot_password.html")

        session["reset_user_id"] = user["id"]
        session["reset_expires"] = time.time() + RESET_WINDOW_SECONDS
        flash("Identity verified. Please set a new password.", "success")
        return redirect(url_for("reset_password"))

    return render_template("forgot_password.html")


@app.route("/reset-password", methods=["GET", "POST"])
def reset_password():
    reset_user_id = session.get("reset_user_id")
    reset_expires = session.get("reset_expires")

    if not reset_user_id or not reset_expires or time.time() > reset_expires:
        session.pop("reset_user_id", None)
        session.pop("reset_expires", None)
        flash("That password reset session has expired. Please verify your identity again.", "error")
        return redirect(url_for("forgot_password"))

    if request.method == "POST":
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        if len(new_password) < 6:
            flash("Password must be at least 6 characters long.", "error")
            return render_template("reset_password.html")

        if new_password != confirm_password:
            flash("Passwords do not match.", "error")
            return render_template("reset_password.html")

        execute_db(
            "UPDATE users SET password_hash = %s WHERE id = %s",
            (generate_password_hash(new_password), reset_user_id),
        )
        session.pop("reset_user_id", None)
        session.pop("reset_expires", None)
        flash("Password updated. Please sign in with your new password.", "success")
        return redirect(url_for("login"))

    return render_template("reset_password.html")


# --------------------------------------------------------------------------
# Intern / Ambassador dashboard
# --------------------------------------------------------------------------
@app.route("/dashboard")
@role_required("intern", "ambassador")
def dashboard():
    user = current_user()
    total = verified_total(user["id"])
    rank_label, amount, next_floor, progress = get_rank(total)

    my_donations = query_db(
        "SELECT * FROM donations WHERE user_id = %s ORDER BY submitted_at DESC", (user["id"],)
    )

    tasks = query_db("SELECT * FROM tasks ORDER BY deadline ASC")
    completed_task_ids = {
        row["task_id"] for row in query_db(
            "SELECT task_id FROM task_completions WHERE user_id = %s", (user["id"],)
        )
    }

    resources = query_db("SELECT * FROM resources ORDER BY category, title")
    leaderboard = org_leaderboard(limit=5)

    return render_template(
        "intern_dashboard.html",
        user=user,
        total=total,
        rank_label=rank_label,
        next_floor=next_floor,
        progress=progress,
        my_donations=my_donations,
        tasks=tasks,
        completed_task_ids=completed_task_ids,
        resources=resources,
        leaderboard=leaderboard,
    )


@app.route("/donations/submit", methods=["POST"])
@role_required("intern", "ambassador")
def submit_donation():
    donor_name = request.form.get("donor_name", "").strip()
    amount = request.form.get("amount", "").strip()
    drive_link = request.form.get("drive_link", "").strip()

    if not donor_name or not amount or not drive_link:
        flash("Please fill in all donation fields.", "error")
        return redirect(url_for("dashboard"))

    try:
        amount_val = float(amount)
        if amount_val <= 0:
            raise ValueError
    except ValueError:
        flash("Please enter a valid donation amount.", "error")
        return redirect(url_for("dashboard"))

    if "drive.google.com" not in drive_link:
        flash("Please attach a valid Google Drive link for verification.", "error")
        return redirect(url_for("dashboard"))

    execute_db(
        """INSERT INTO donations (user_id, donor_name, amount, drive_link, status)
           VALUES (%s, %s, %s, %s, 'pending')""",
        (session["user_id"], donor_name, amount_val, drive_link),
    )
    flash("Donation submitted for verification!", "success")
    return redirect(url_for("dashboard"))


@app.route("/tasks/<int:task_id>/complete", methods=["POST"])
@role_required("intern", "ambassador")
def complete_task(task_id):
    existing = query_db(
        "SELECT id FROM task_completions WHERE task_id = %s AND user_id = %s",
        (task_id, session["user_id"]), one=True,
    )
    if existing is None:
        execute_db(
            "INSERT INTO task_completions (task_id, user_id) VALUES (%s, %s)",
            (task_id, session["user_id"]),
        )
        flash("Task marked as complete. Great work!", "success")
    return redirect(url_for("dashboard"))


# --------------------------------------------------------------------------
# Admin panel
# --------------------------------------------------------------------------
@app.route("/admin")
@role_required("admin")
def admin_panel():
    donations = query_db(
        """SELECT d.*, u.full_name, u.username, u.role
           FROM donations d JOIN users u ON u.id = d.user_id
           ORDER BY d.submitted_at DESC"""
    )
    interns = query_db(
        "SELECT * FROM users WHERE role = 'intern' ORDER BY full_name"
    )
    ambassadors = query_db(
        "SELECT * FROM users WHERE role = 'ambassador' ORDER BY full_name"
    )
    tasks = query_db("SELECT * FROM tasks ORDER BY deadline ASC")
    resources = query_db("SELECT * FROM resources ORDER BY category, title")
    leaderboard = org_leaderboard()

    stats = query_db(
        """SELECT
             COUNT(*) FILTER (WHERE status = 'pending') AS pending_count,
             COUNT(*) FILTER (WHERE status = 'approved') AS approved_count,
             COUNT(*) FILTER (WHERE status = 'rejected') AS rejected_count,
             COALESCE(SUM(amount) FILTER (WHERE status = 'approved'), 0) AS verified_total
           FROM donations""",
        one=True,
    )

    return render_template(
        "admin_dashboard.html",
        donations=donations,
        interns=interns,
        ambassadors=ambassadors,
        tasks=tasks,
        resources=resources,
        leaderboard=leaderboard,
        stats=stats,
    )


@app.route("/admin/donations/<int:donation_id>/review", methods=["POST"])
@role_required("admin")
def review_donation(donation_id):
    decision = request.form.get("decision")
    note = request.form.get("admin_note", "").strip()

    if decision not in ("approved", "rejected"):
        flash("Invalid review decision.", "error")
        return redirect(url_for("admin_panel"))

    execute_db(
        """UPDATE donations SET status = %s, admin_note = %s, reviewed_at = %s
           WHERE id = %s""",
        (decision, note if decision == "rejected" else None, datetime.now(), donation_id),
    )
    flash(f"Donation #{donation_id} marked as {decision}.", "success")
    return redirect(url_for("admin_panel"))


@app.route("/admin/export.csv")
@role_required("admin")
def export_csv():
    rows = query_db(
        """SELECT d.id, u.full_name, u.username, u.role, d.donor_name, d.amount,
                  d.status, d.drive_link, d.admin_note, d.submitted_at, d.reviewed_at
           FROM donations d JOIN users u ON u.id = d.user_id
           ORDER BY d.submitted_at DESC"""
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Donation ID", "Volunteer Name", "Username", "Role", "Donor Name",
        "Amount (INR)", "Status", "Drive Link", "Admin Note", "Submitted At", "Reviewed At",
    ])
    for r in rows:
        writer.writerow([r[k] for k in r.keys()])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=bhumi_donation_ledger.csv"},
    )


# --- Users (Interns / Campus Ambassadors) ---------------------------------
@app.route("/admin/users/create", methods=["POST"])
@role_required("admin")
def create_user():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    full_name = request.form.get("full_name", "").strip()
    role = request.form.get("role", "").strip()
    email = request.form.get("email", "").strip()
    phone = request.form.get("phone", "").strip()
    tenure_start = request.form.get("tenure_start") or None
    tenure_end = request.form.get("tenure_end") or None

    if not username or not password or not full_name or role not in MANAGEABLE_ROLES:
        flash("Please fill in all required fields correctly.", "error")
        return redirect(url_for("admin_panel"))

    existing = query_db("SELECT id FROM users WHERE username = %s", (username,), one=True)
    if existing:
        flash("That username already exists.", "error")
        return redirect(url_for("admin_panel"))

    execute_db(
        """INSERT INTO users (username, password_hash, role, full_name, email, phone, tenure_start, tenure_end)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
        (username, generate_password_hash(password), role, full_name, email, phone, tenure_start, tenure_end),
    )
    flash(f"Account created for {full_name}.", "success")
    return redirect(url_for("admin_panel"))


@app.route("/admin/users/<int:user_id>/edit", methods=["POST"])
@role_required("admin")
def edit_user(user_id):
    target = query_db("SELECT * FROM users WHERE id = %s", (user_id,), one=True)
    if target is None or target["role"] not in MANAGEABLE_ROLES:
        flash("That account cannot be edited.", "error")
        return redirect(url_for("admin_panel"))

    full_name = request.form.get("full_name", "").strip()
    username = request.form.get("username", "").strip()
    role = request.form.get("role", "").strip()
    email = request.form.get("email", "").strip()
    phone = request.form.get("phone", "").strip()
    tenure_start = request.form.get("tenure_start") or None
    tenure_end = request.form.get("tenure_end") or None
    new_password = request.form.get("password", "").strip()

    if not full_name or not username or role not in MANAGEABLE_ROLES:
        flash("Please fill in all required fields correctly.", "error")
        return redirect(url_for("admin_panel"))

    existing = query_db(
        "SELECT id FROM users WHERE username = %s AND id != %s", (username, user_id), one=True
    )
    if existing:
        flash("That username is already taken by another account.", "error")
        return redirect(url_for("admin_panel"))

    if new_password:
        execute_db(
            """UPDATE users SET full_name = %s, username = %s, role = %s, email = %s,
                                 phone = %s, tenure_start = %s, tenure_end = %s, password_hash = %s
               WHERE id = %s""",
            (full_name, username, role, email, phone, tenure_start, tenure_end,
             generate_password_hash(new_password), user_id),
        )
    else:
        execute_db(
            """UPDATE users SET full_name = %s, username = %s, role = %s, email = %s,
                                 phone = %s, tenure_start = %s, tenure_end = %s
               WHERE id = %s""",
            (full_name, username, role, email, phone, tenure_start, tenure_end, user_id),
        )
    flash(f"Account updated for {full_name}.", "success")
    return redirect(url_for("admin_panel"))


@app.route("/admin/users/<int:user_id>/delete", methods=["POST"])
@role_required("admin")
def delete_user(user_id):
    target = query_db("SELECT * FROM users WHERE id = %s", (user_id,), one=True)
    if target is None or target["role"] not in MANAGEABLE_ROLES:
        flash("That account cannot be deleted.", "error")
        return redirect(url_for("admin_panel"))

    execute_db("DELETE FROM users WHERE id = %s", (user_id,))
    flash(f"Account for {target['full_name']} has been removed.", "success")
    return redirect(url_for("admin_panel"))


# --- Missions (tasks) ------------------------------------------------------
@app.route("/admin/tasks/create", methods=["POST"])
@role_required("admin")
def create_task():
    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    deadline = request.form.get("deadline") or None

    if not title:
        flash("Mission title is required.", "error")
        return redirect(url_for("admin_panel"))

    execute_db(
        "INSERT INTO tasks (title, description, deadline, created_by) VALUES (%s, %s, %s, %s)",
        (title, description, deadline, session["user_id"]),
    )
    flash("New mission published to all volunteers.", "success")
    return redirect(url_for("admin_panel"))


@app.route("/admin/tasks/<int:task_id>/edit", methods=["POST"])
@role_required("admin")
def edit_task(task_id):
    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    deadline = request.form.get("deadline") or None

    if not title:
        flash("Mission title is required.", "error")
        return redirect(url_for("admin_panel"))

    execute_db(
        "UPDATE tasks SET title = %s, description = %s, deadline = %s WHERE id = %s",
        (title, description, deadline, task_id),
    )
    flash("Mission updated.", "success")
    return redirect(url_for("admin_panel"))


@app.route("/admin/tasks/<int:task_id>/delete", methods=["POST"])
@role_required("admin")
def delete_task(task_id):
    execute_db("DELETE FROM tasks WHERE id = %s", (task_id,))
    flash("Mission deleted.", "success")
    return redirect(url_for("admin_panel"))


# --- Resources --------------------------------------------------------------
@app.route("/admin/resources/create", methods=["POST"])
@role_required("admin")
def create_resource():
    title = request.form.get("title", "").strip()
    category = request.form.get("category", "").strip()
    link = request.form.get("link", "").strip()

    if not title or not category or not link:
        flash("Please fill in all resource fields.", "error")
        return redirect(url_for("admin_panel"))

    execute_db(
        "INSERT INTO resources (title, category, link) VALUES (%s, %s, %s)",
        (title, category, link),
    )
    flash("Resource added to the library.", "success")
    return redirect(url_for("admin_panel"))


@app.route("/admin/resources/<int:resource_id>/edit", methods=["POST"])
@role_required("admin")
def edit_resource(resource_id):
    title = request.form.get("title", "").strip()
    category = request.form.get("category", "").strip()
    link = request.form.get("link", "").strip()

    if not title or not category or not link:
        flash("Please fill in all resource fields.", "error")
        return redirect(url_for("admin_panel"))

    execute_db(
        "UPDATE resources SET title = %s, category = %s, link = %s WHERE id = %s",
        (title, category, link, resource_id),
    )
    flash("Resource updated.", "success")
    return redirect(url_for("admin_panel"))


@app.route("/admin/resources/<int:resource_id>/delete", methods=["POST"])
@role_required("admin")
def delete_resource(resource_id):
    execute_db("DELETE FROM resources WHERE id = %s", (resource_id,))
    flash("Resource removed from the library.", "success")
    return redirect(url_for("admin_panel"))


# --------------------------------------------------------------------------
# Template filters
# --------------------------------------------------------------------------
@app.context_processor
def inject_now():
    return {"now": datetime.now()}


@app.template_filter("inr")
def inr_format(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return value
    return f"₹{value:,.0f}"


if __name__ == "__main__":
    if not os.environ.get("DATABASE_URL"):
        print("DATABASE_URL is not set. Set it to your Supabase/PostgreSQL connection string,")
        print("then run `python init_db.py` once before starting the app.")
    app.run(debug=True, host="0.0.0.0", port=5000)
