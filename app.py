import io
import json
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
from functools import wraps

from flask import (Flask, flash, g, redirect, render_template, request,
                    session, url_for, Response, jsonify)
from werkzeug.security import check_password_hash, generate_password_hash
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from pywebpush import webpush, WebPushException

app = Flask(__name__)
app.secret_key = os.environ.get("BHUMI_SECRET_KEY", "dev-secret-key-change-in-production")

# --------------------------------------------------------------------------
# Web Push (PWA notifications) configuration
# --------------------------------------------------------------------------
# These defaults are a real, working VAPID key pair generated for this
# project so notifications work out of the box. For a production deployment,
# generate your own pair (see README) and set these as environment variables
# instead — anyone with the private key could send push notifications
# claiming to be your app.
VAPID_PUBLIC_KEY = os.environ.get(
    "VAPID_PUBLIC_KEY",
    "BOogVH8cVKg0RB1ubr2P9wQvdTNaM--PVqpCM1Uz2NWsMI4wbqLmij-RYlHVkE7fXBMI-Y4njrOqAbt_IQeNLvA",
)
VAPID_PRIVATE_KEY = os.environ.get(
    "VAPID_PRIVATE_KEY",
    "s8Xk1zzCvQdc7Q0W8oJWgT_6y2op1gVRW5JPWQgtHxQ",
)
VAPID_CLAIM_EMAIL = os.environ.get("VAPID_CLAIM_EMAIL", "mailto:admin@bhumi.ngo")

# Rank tiers: (label, floor amount, ceiling amount or None for top tier)
RANK_TIERS = [
    ("Bronze", 0, 5000),
    ("Silver", 5000, 15000),
    ("Gold", 15000, 50000),
    ("Platinum", 50000, None),
]


# --------------------------------------------------------------------------
# Database helpers
# --------------------------------------------------------------------------
def get_db():
    if "db" not in g:
        database_url = os.environ.get('DATABASE_URL')
        if not database_url:
            raise RuntimeError(
                "DATABASE_URL environment variable is not set. "
                "Set it in your hosting provider's Environment settings to your Supabase "
                "connection string, then redeploy/restart."
            )
        g.db = psycopg2.connect(
            database_url,
            cursor_factory=RealDictCursor
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
                # Fix: Route users to their correct respective homepages
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


def get_campaigns_with_progress():
    """Returns all campaign goals with progress computed from verified
    donations explicitly tagged to that campaign (via donations.campaign_id)."""
    campaigns = query_db("SELECT * FROM campaign_goals ORDER BY start_date DESC NULLS LAST, id DESC")
    today = datetime.now().date()
    results = []
    for c in campaigns:
        raised = query_db(
            "SELECT COALESCE(SUM(amount), 0) AS total FROM donations WHERE status = 'approved' AND campaign_id = %s",
            (c["id"],), one=True,
        )["total"]

        progress_pct = min(100.0, (raised / c["target_amount"]) * 100) if c["target_amount"] else 0
        is_active = (not c["start_date"] or c["start_date"] <= today) and (not c["end_date"] or today <= c["end_date"])

        results.append({
            **dict(c),
            "raised": raised,
            "progress_pct": progress_pct,
            "is_active": is_active,
        })
    return results


def send_push_notification(user_ids, title, body, url="/"):
    """Sends a Web Push notification to every subscribed device for the
    given user id(s). Silently skips/cleans up subscriptions that the push
    service reports as gone, and never lets a delivery failure break the
    calling request (e.g. donation submission still succeeds even if every
    push attempt fails)."""
    if not user_ids:
        return
    if isinstance(user_ids, int):
        user_ids = [user_ids]

    placeholders = ",".join(["%s"] * len(user_ids))
    subs = query_db(
        f"SELECT * FROM push_subscriptions WHERE user_id IN ({placeholders})",
        tuple(user_ids),
    )

    payload = json.dumps({"title": title, "body": body, "url": url})

    for sub in subs:
        subscription_info = {
            "endpoint": sub["endpoint"],
            "keys": {"p256dh": sub["p256dh"], "auth": sub["auth"]},
        }
        try:
            webpush(
                subscription_info=subscription_info,
                data=payload,
                vapid_private_key=VAPID_PRIVATE_KEY,
                vapid_claims={"sub": VAPID_CLAIM_EMAIL},
            )
        except WebPushException as e:
            status = getattr(e.response, "status_code", None)
            if status in (404, 410):
                # Subscription is gone (browser data cleared, uninstalled, etc.) — clean it up.
                execute_db("DELETE FROM push_subscriptions WHERE id = %s", (sub["id"],))
            else:
                app.logger.warning("Push notification failed: %s", e)
        except Exception as e:
            app.logger.warning("Push notification error: %s", e)


# --------------------------------------------------------------------------
# Auth routes
# --------------------------------------------------------------------------
@app.route("/")
def index():
    if "user_id" in session:
        # Fix: Direct admins to the admin panel, everyone else to dashboard
        if session.get("role") == "admin":
            dest = url_for("admin_panel")
        else:
            dest = url_for("dashboard")
    else:
        dest = url_for("login")
    return render_template("splash.html", dest=dest)


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


@app.route("/sw.js")
def service_worker():
    """Served from the root path (not /static/) so its default scope covers
    the whole site rather than just /static/."""
    return app.send_static_file("sw.js")


@app.route("/push/subscribe", methods=["POST"])
@login_required
def push_subscribe():
    data = request.get_json(silent=True) or {}
    endpoint = data.get("endpoint")
    keys = data.get("keys", {})
    p256dh = keys.get("p256dh")
    auth = keys.get("auth")

    if not endpoint or not p256dh or not auth:
        return jsonify({"error": "Invalid subscription payload"}), 400

    existing = query_db("SELECT id FROM push_subscriptions WHERE endpoint = %s", (endpoint,), one=True)
    if existing:
        execute_db(
            "UPDATE push_subscriptions SET user_id = %s, p256dh = %s, auth = %s WHERE endpoint = %s",
            (session["user_id"], p256dh, auth, endpoint),
        )
    else:
        execute_db(
            "INSERT INTO push_subscriptions (user_id, endpoint, p256dh, auth) VALUES (%s, %s, %s, %s)",
            (session["user_id"], endpoint, p256dh, auth),
        )
    return jsonify({"status": "subscribed"})


@app.route("/push/unsubscribe", methods=["POST"])
@login_required
def push_unsubscribe():
    data = request.get_json(silent=True) or {}
    endpoint = data.get("endpoint")
    if endpoint:
        execute_db("DELETE FROM push_subscriptions WHERE endpoint = %s AND user_id = %s", (endpoint, session["user_id"]))
    return jsonify({"status": "unsubscribed"})


@app.route("/forgot-password")
def forgot_password():
    # Password resets are now handled by contacting an admin directly (see the
    # modal on the login page) rather than a self-service flow, since there's
    # no email service to safely verify identity through. This route is kept
    # only so any old bookmarked/shared links don't 404.
    return redirect(url_for("login"))


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
        """SELECT d.*, c.title AS campaign_title
           FROM donations d
           LEFT JOIN campaign_goals c ON c.id = d.campaign_id
           WHERE d.user_id = %s ORDER BY d.submitted_at DESC""",
        (user["id"],),
    )

    tasks = query_db("SELECT * FROM tasks ORDER BY deadline ASC")
    completed_task_ids = {
        row["task_id"] for row in query_db(
            "SELECT task_id FROM task_completions WHERE user_id = %s", (user["id"],)
        )
    }

    resources = query_db("SELECT * FROM resources ORDER BY category, title")

    leaderboard = query_db(
        """SELECT u.full_name, u.role, COALESCE(SUM(d.amount), 0) AS total
           FROM users u
           LEFT JOIN donations d ON d.user_id = u.id AND d.status = 'approved'
           WHERE u.role IN ('intern', 'ambassador')
           GROUP BY u.id
           ORDER BY total DESC
           LIMIT 5"""
    )

    announcements = query_db(
        "SELECT * FROM announcements ORDER BY created_at DESC LIMIT 5"
    )

    campaigns = get_campaigns_with_progress()

    return render_template(
        "intern_dashboard.html",
        user=user,
        total=total,
        campaigns=campaigns,
        rank_label=rank_label,
        next_floor=next_floor,
        progress=progress,
        my_donations=my_donations,
        tasks=tasks,
        completed_task_ids=completed_task_ids,
        resources=resources,
        leaderboard=leaderboard,
        announcements=announcements,
    )


@app.route("/donations/submit", methods=["POST"])
@role_required("intern", "ambassador")
def submit_donation():
    donor_name = request.form.get("donor_name", "").strip()
    donor_phone = request.form.get("donor_phone", "").strip()
    amount = request.form.get("amount", "").strip()
    drive_link = request.form.get("drive_link", "").strip()
    utr_reference = request.form.get("utr_reference", "").strip()
    campaign_id_raw = request.form.get("campaign_id", "").strip()

    if not donor_name or not donor_phone or not amount or not drive_link or not utr_reference:
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

    campaign_id = None
    if campaign_id_raw:
        try:
            campaign_id_candidate = int(campaign_id_raw)
        except ValueError:
            campaign_id_candidate = None
        if campaign_id_candidate and query_db(
            "SELECT id FROM campaign_goals WHERE id = %s", (campaign_id_candidate,), one=True
        ):
            campaign_id = campaign_id_candidate

    execute_db(
        """INSERT INTO donations (user_id, donor_name, donor_phone, amount, drive_link, utr_reference, campaign_id, status)
           VALUES (%s, %s, %s, %s, %s, %s, %s, 'pending')""",
        (session["user_id"], donor_name, donor_phone, amount_val, drive_link, utr_reference, campaign_id),
    )

    admin_ids = [r["id"] for r in query_db("SELECT id FROM users WHERE role = 'admin'")]
    send_push_notification(
        admin_ids,
        "💰 New donation to verify",
        f"{session.get('full_name')} logged {donor_name}'s donation of ₹{amount_val:,.0f} — awaiting approval.",
        url=url_for("admin_panel"),
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


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    user = current_user()

    if request.method == "POST":
        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not check_password_hash(user["password_hash"], current_password):
            flash("Your current password is incorrect.", "error")
        elif len(new_password) < 6:
            flash("New password must be at least 6 characters.", "error")
        elif new_password != confirm_password:
            flash("New password and confirmation don't match.", "error")
        else:
            execute_db(
                "UPDATE users SET password_hash = %s WHERE id = %s",
                (generate_password_hash(new_password), user["id"]),
            )
            flash("Password updated successfully.", "success")
            return redirect(url_for("profile"))

    total = verified_total(user["id"]) if user["role"] in ("intern", "ambassador") else None
    rank_label = get_rank(total)[0] if total is not None else None

    return render_template("profile.html", user=user, total=total, rank_label=rank_label)


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
    users = query_db(
        """SELECT u.*, m.full_name AS manager_name
           FROM users u
           LEFT JOIN users m ON m.id = u.assigned_admin_id
           WHERE u.role != 'admin'
           ORDER BY u.full_name"""
    )
    admins = query_db("SELECT * FROM users WHERE role = 'admin' ORDER BY full_name")
    tasks = query_db("SELECT * FROM tasks ORDER BY deadline ASC")
    resources = query_db("SELECT * FROM resources ORDER BY category, title")

    stats = query_db(
        """SELECT
             COUNT(*) FILTER (WHERE status = 'pending') AS pending_count,
             COUNT(*) FILTER (WHERE status = 'approved') AS approved_count,
             COUNT(*) FILTER (WHERE status = 'rejected') AS rejected_count,
             COALESCE(SUM(amount) FILTER (WHERE status = 'approved'), 0) AS verified_total
           FROM donations""",
        one=True,
    )

    admin_leaderboard = query_db(
        """SELECT u.full_name, u.role, COALESCE(SUM(d.amount), 0) AS total
           FROM users u
           LEFT JOIN donations d ON d.user_id = u.id AND d.status = 'approved'
           WHERE u.role IN ('intern', 'ambassador')
           GROUP BY u.id
           ORDER BY total DESC"""
    )

    announcements = query_db("SELECT * FROM announcements ORDER BY created_at DESC")

    campaigns = get_campaigns_with_progress()

    return render_template(
        "admin_dashboard.html",
        donations=donations,
        users=users,
        admins=admins,
        tasks=tasks,
        resources=resources,
        stats=stats,
        admin_leaderboard=admin_leaderboard,
        announcements=announcements,
        campaigns=campaigns,
    )


@app.route("/admin/donations/<int:donation_id>/review", methods=["POST"])
@role_required("admin")
def review_donation(donation_id):
    decision = request.form.get("decision")
    note = request.form.get("admin_note", "").strip()

    if decision not in ("approved", "rejected"):
        flash("Invalid review decision.", "error")
        return redirect(url_for("admin_panel"))

    donation = query_db("SELECT * FROM donations WHERE id = %s", (donation_id,), one=True)

    execute_db(
        """UPDATE donations SET status = %s, admin_note = %s, reviewed_at = %s
           WHERE id = %s""",
        (decision, note if decision == "rejected" else None, datetime.now(), donation_id),
    )

    if donation:
        if decision == "approved":
            send_push_notification(
                donation["user_id"],
                "✅ Donation approved",
                f"Your donation from {donation['donor_name']} (₹{donation['amount']:,.0f}) has been verified.",
                url=url_for("dashboard"),
            )
        else:
            send_push_notification(
                donation["user_id"],
                "❌ Donation needs attention",
                f"Your donation from {donation['donor_name']} was rejected: {note or 'see dashboard for details'}",
                url=url_for("dashboard"),
            )

    flash(f"Donation #{donation_id} marked as {decision}.", "success")
    return redirect(url_for("admin_panel"))


@app.route("/admin/export.pdf")
@role_required("admin")
def export_pdf():
    start_date = request.args.get("start_date", "").strip()
    end_date = request.args.get("end_date", "").strip()

    query = """SELECT d.id, u.full_name, d.donor_name, d.donor_phone, d.amount,
                      d.utr_reference, d.status, d.submitted_at
               FROM donations d JOIN users u ON u.id = d.user_id"""
    conditions = []
    params = []
    if start_date:
        conditions.append("d.submitted_at >= %s")
        params.append(start_date)
    if end_date:
        conditions.append("d.submitted_at < (%s::date + INTERVAL '1 day')")
        params.append(end_date)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY d.submitted_at DESC"

    rows = query_db(query, tuple(params))

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=landscape(A4),
        topMargin=36, bottomMargin=36, leftMargin=36, rightMargin=36,
    )
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("Bhumi Patna &mdash; Donation Ledger", styles["Title"]))
    range_label = "All time"
    if start_date or end_date:
        range_label = f"{start_date or 'earliest'} to {end_date or 'latest'}"
    elements.append(Paragraph(f"Date range: {range_label}", styles["Normal"]))
    elements.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles["Normal"]))
    elements.append(Spacer(1, 16))

    total_verified = sum(r["amount"] for r in rows if r["status"] == "approved")
    elements.append(Paragraph(
        f"Total entries: {len(rows)}   |   Verified total: Rs. {total_verified:,.0f}",
        styles["Normal"],
    ))
    elements.append(Spacer(1, 12))

    table_data = [["Date", "Volunteer", "Donor", "Phone", "Amount (INR)", "UTR/Txn ID", "Status"]]
    for r in rows:
        table_data.append([
            str(r["submitted_at"])[:16],
            r["full_name"],
            r["donor_name"],
            r["donor_phone"] or "-",
            f"{r['amount']:,.0f}",
            r["utr_reference"] or "-",
            r["status"].capitalize(),
        ])

    if len(table_data) == 1:
        elements.append(Paragraph("No donations found for this date range.", styles["Normal"]))
    else:
        table = Table(table_data, repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2872a")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e8e3d8")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#faf9f6")]),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        elements.append(table)

    doc.build(elements)
    buffer.seek(0)

    return Response(
        buffer.read(),
        mimetype="application/pdf",
        headers={"Content-Disposition": "attachment; filename=bhumi_donation_ledger.pdf"},
    )


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
    assigned_admin_id = request.form.get("assigned_admin_id") or None

    if not username or not password or not full_name or not email or role not in ("admin", "intern", "ambassador"):
        flash("Please fill in all required fields correctly (email is required for password resets).", "error")
        return redirect(url_for("admin_panel"))

    existing = query_db("SELECT id FROM users WHERE username = %s", (username,), one=True)
    if existing:
        flash("That username already exists.", "error")
        return redirect(url_for("admin_panel"))

    # Admin accounts don't have tenure dates or a manager of their own.
    if role == "admin":
        tenure_start = tenure_end = assigned_admin_id = None

    execute_db(
        """INSERT INTO users (username, password_hash, role, full_name, email, phone, tenure_start, tenure_end, assigned_admin_id)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (username, generate_password_hash(password), role, full_name, email, phone, tenure_start, tenure_end, assigned_admin_id),
    )
    flash(f"Account created for {full_name}.", "success")
    return redirect(url_for("admin_panel"))


@app.route("/admin/users/<int:user_id>/edit", methods=["POST"])
@role_required("admin")
def edit_user(user_id):
    full_name = request.form.get("full_name", "").strip()
    email = request.form.get("email", "").strip()
    phone = request.form.get("phone", "").strip()
    tenure_start = request.form.get("tenure_start") or None
    tenure_end = request.form.get("tenure_end") or None
    assigned_admin_id = request.form.get("assigned_admin_id") or None
    new_password = request.form.get("new_password", "").strip()

    if not full_name or not email:
        flash("Full name and email are required.", "error")
        return redirect(url_for("admin_panel"))

    target = query_db("SELECT role FROM users WHERE id = %s", (user_id,), one=True)
    if target and target["role"] == "admin":
        assigned_admin_id = None  # admins aren't managed by another admin

    if new_password:
        execute_db(
            """UPDATE users SET full_name = %s, email = %s, phone = %s,
                   tenure_start = %s, tenure_end = %s, assigned_admin_id = %s, password_hash = %s
               WHERE id = %s""",
            (full_name, email, phone, tenure_start, tenure_end, assigned_admin_id,
             generate_password_hash(new_password), user_id),
        )
    else:
        execute_db(
            """UPDATE users SET full_name = %s, email = %s, phone = %s,
                   tenure_start = %s, tenure_end = %s, assigned_admin_id = %s
               WHERE id = %s""",
            (full_name, email, phone, tenure_start, tenure_end, assigned_admin_id, user_id),
        )

    flash(f"Updated {full_name}'s account.", "success")
    return redirect(url_for("admin_panel"))


@app.route("/admin/users/<int:user_id>/delete", methods=["POST"])
@role_required("admin")
def delete_user(user_id):
    target = query_db("SELECT full_name, role FROM users WHERE id = %s", (user_id,), one=True)
    if target is None:
        flash("That account no longer exists.", "error")
        return redirect(url_for("admin_panel"))

    if target["role"] == "admin":
        if user_id == session["user_id"]:
            flash("You can't delete your own account while logged in as it.", "error")
            return redirect(url_for("admin_panel"))
        admin_count = query_db("SELECT COUNT(*) AS count FROM users WHERE role = 'admin'", one=True)["count"]
        if admin_count <= 1:
            flash("Can't delete the only remaining admin account.", "error")
            return redirect(url_for("admin_panel"))
        # Unassign any interns/ambassadors this admin was managing.
        execute_db("UPDATE users SET assigned_admin_id = NULL WHERE assigned_admin_id = %s", (user_id,))

    # Remove dependent records first so the delete doesn't hit a foreign-key constraint.
    execute_db("DELETE FROM task_completions WHERE user_id = %s", (user_id,))
    execute_db("DELETE FROM donations WHERE user_id = %s", (user_id,))
    execute_db("DELETE FROM users WHERE id = %s", (user_id,))

    flash(f"Removed {target['full_name']}'s account.", "success")
    return redirect(url_for("admin_panel"))


@app.route("/admin/tasks/create", methods=["POST"])
@role_required("admin")
def create_task():
    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    deadline = request.form.get("deadline") or None

    if not title:
        flash("Task title is required.", "error")
        return redirect(url_for("admin_panel"))

    execute_db(
        "INSERT INTO tasks (title, description, deadline, created_by) VALUES (%s, %s, %s, %s)",
        (title, description, deadline, session["user_id"]),
    )

    volunteer_ids = [r["id"] for r in query_db("SELECT id FROM users WHERE role IN ('intern', 'ambassador')")]
    send_push_notification(volunteer_ids, "🎯 New mission", title, url=url_for("dashboard"))

    flash("New mission published to all volunteers.", "success")
    return redirect(url_for("admin_panel"))


@app.route("/admin/tasks/<int:task_id>/edit", methods=["POST"])
@role_required("admin")
def edit_task(task_id):
    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    deadline = request.form.get("deadline") or None

    if not title:
        flash("Task title is required.", "error")
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
    execute_db("DELETE FROM task_completions WHERE task_id = %s", (task_id,))
    execute_db("DELETE FROM tasks WHERE id = %s", (task_id,))
    flash("Mission deleted.", "success")
    return redirect(url_for("admin_panel"))


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
    flash("Resource deleted.", "success")
    return redirect(url_for("admin_panel"))


@app.route("/admin/announcements/create", methods=["POST"])
@role_required("admin")
def create_announcement():
    title = request.form.get("title", "").strip()
    message = request.form.get("message", "").strip()

    if not title or not message:
        flash("Please fill in both the title and message.", "error")
        return redirect(url_for("admin_panel"))

    execute_db(
        "INSERT INTO announcements (title, message, created_by) VALUES (%s, %s, %s)",
        (title, message, session["user_id"]),
    )

    volunteer_ids = [r["id"] for r in query_db("SELECT id FROM users WHERE role IN ('intern', 'ambassador')")]
    send_push_notification(volunteer_ids, f"📢 {title}", message, url=url_for("dashboard"))

    flash("Announcement posted.", "success")
    return redirect(url_for("admin_panel"))


@app.route("/admin/announcements/<int:announcement_id>/delete", methods=["POST"])
@role_required("admin")
def delete_announcement(announcement_id):
    execute_db("DELETE FROM announcements WHERE id = %s", (announcement_id,))
    flash("Announcement removed.", "success")
    return redirect(url_for("admin_panel"))


@app.route("/admin/campaigns/create", methods=["POST"])
@role_required("admin")
def create_campaign():
    title = request.form.get("title", "").strip()
    target_amount = request.form.get("target_amount", "").strip()
    start_date = request.form.get("start_date") or None
    end_date = request.form.get("end_date") or None

    if not title or not target_amount:
        flash("Please provide a campaign title and target amount.", "error")
        return redirect(url_for("admin_panel"))

    try:
        target_val = float(target_amount)
        if target_val <= 0:
            raise ValueError
    except ValueError:
        flash("Please enter a valid target amount.", "error")
        return redirect(url_for("admin_panel"))

    execute_db(
        "INSERT INTO campaign_goals (title, target_amount, start_date, end_date, created_by) VALUES (%s, %s, %s, %s, %s)",
        (title, target_val, start_date, end_date, session["user_id"]),
    )
    flash("Campaign goal created.", "success")
    return redirect(url_for("admin_panel"))


@app.route("/admin/campaigns/<int:campaign_id>/edit", methods=["POST"])
@role_required("admin")
def edit_campaign(campaign_id):
    title = request.form.get("title", "").strip()
    target_amount = request.form.get("target_amount", "").strip()
    start_date = request.form.get("start_date") or None
    end_date = request.form.get("end_date") or None

    if not title or not target_amount:
        flash("Please provide a campaign title and target amount.", "error")
        return redirect(url_for("admin_panel"))

    try:
        target_val = float(target_amount)
        if target_val <= 0:
            raise ValueError
    except ValueError:
        flash("Please enter a valid target amount.", "error")
        return redirect(url_for("admin_panel"))

    execute_db(
        "UPDATE campaign_goals SET title = %s, target_amount = %s, start_date = %s, end_date = %s WHERE id = %s",
        (title, target_val, start_date, end_date, campaign_id),
    )
    flash("Campaign goal updated.", "success")
    return redirect(url_for("admin_panel"))


@app.route("/admin/campaigns/<int:campaign_id>/delete", methods=["POST"])
@role_required("admin")
def delete_campaign(campaign_id):
    execute_db("DELETE FROM campaign_goals WHERE id = %s", (campaign_id,))
    flash("Campaign goal deleted.", "success")
    return redirect(url_for("admin_panel"))


# --------------------------------------------------------------------------
# Template filters
# --------------------------------------------------------------------------
@app.context_processor
def inject_now():
    return {"now": datetime.now(), "vapid_public_key": VAPID_PUBLIC_KEY}


@app.template_filter("inr")
def inr_format(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return value
    return f"₹{value:,.0f}"


_AVATAR_PALETTE = [
    "#e2872a", "#6fa83c", "#c0392b", "#45529c",
    "#a4790f", "#2f6b1f", "#8a5a2b", "#52606d",
]


@app.template_filter("initials")
def initials_filter(name):
    if not name:
        return "?"
    parts = [p for p in name.strip().split() if p]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][0].upper()
    return (parts[0][0] + parts[-1][0]).upper()


@app.template_filter("avatar_color")
def avatar_color_filter(name):
    if not name:
        return _AVATAR_PALETTE[0]
    return _AVATAR_PALETTE[sum(ord(c) for c in name) % len(_AVATAR_PALETTE)]


if __name__ == "__main__":
    if not os.environ.get("DATABASE_URL"):
        print("DATABASE_URL is not set. Run `export DATABASE_URL=...` then `python init_db.py --if-missing` before starting the app.")
    app.run(debug=True, host="0.0.0.0", port=5000)
