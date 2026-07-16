"""
Initializes PostgreSQL database from schema.sql and seeds it with a demo admin account,
a few intern/ambassador accounts, sample tasks, resources and donations.
Run this once before starting the app:  python init_db.py
"""
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import date, timedelta
from werkzeug.security import generate_password_hash

SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")

def init_db(if_missing_only=False):
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL environment variable is not set. "
            "Set it in your Render service's Environment settings to your Supabase "
            "connection string (Project Settings -> Database -> Connection string in Supabase), "
            "then redeploy."
        )

    # Connect to PostgreSQL using the DATABASE_URL environment variable
    conn = psycopg2.connect(
        database_url,
        cursor_factory=RealDictCursor
    )
    cur = conn.cursor()

    # psycopg2 executes SQL files directly via the cursor
    with open(SCHEMA_PATH, "r") as f:
        cur.execute(f.read())
    conn.commit()

    if if_missing_only:
        cur.execute("SELECT COUNT(*) AS count FROM users")
        if cur.fetchone()["count"] > 0:
            print("Database already has data — skipping re-seed.")
            cur.close()
            conn.close()
            return

    today = date.today()

    # --- Users -----------------------------------------------------------
    # Each tuple's last element is the username of the admin who manages
    # them (or None if unmanaged/not applicable — only meaningful for
    # intern/ambassador accounts).
    users = [
        ("admin", "Admin@123", "admin", "Bhumi Admin", "admin@bhumi.ngo", "9999900000", None, None, None),
        ("admin.regional", "Admin@123", "admin", "Regional Admin (Patna Team)", "regional.admin@bhumi.ngo", "9999900001", None, None, None),
        ("priya.sharma", "Intern@123", "intern", "Priya Sharma", "priya@example.com", "9876500001",
         today - timedelta(days=20), today + timedelta(days=40), "admin.regional"),
        ("rahul.verma", "Intern@123", "intern", "Rahul Verma", "rahul@example.com", "9876500002",
         today - timedelta(days=10), today + timedelta(days=50), "admin.regional"),
        ("ananya.das", "Ambassador@123", "ambassador", "Ananya Das", "ananya@example.com", "9876500003",
         today - timedelta(days=35), today + timedelta(days=10), None),
        ("karan.mehta", "Ambassador@123", "ambassador", "Karan Mehta", "karan@example.com", "9876500004",
         today - timedelta(days=5), today + timedelta(days=85), None),
        ("sneha.iyer", "Intern@123", "intern", "Sneha Iyer", "sneha@example.com", "9876500005",
         today - timedelta(days=15), today + timedelta(days=2), "admin.regional"),
    ]

    user_ids = {}
    manager_assignments = []
    for uname, pwd, role, name, email, phone, t_start, t_end, manager_uname in users:
        # Replaced cur.lastrowid with PostgreSQL 'RETURNING id'
        cur.execute(
            """INSERT INTO users (username, password_hash, role, full_name, email, phone, tenure_start, tenure_end)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
            (uname, generate_password_hash(pwd), role, name, email, phone, t_start, t_end),
        )
        user_ids[uname] = cur.fetchone()['id']
        if manager_uname:
            manager_assignments.append((uname, manager_uname))

    for uname, manager_uname in manager_assignments:
        cur.execute(
            "UPDATE users SET assigned_admin_id = %s WHERE id = %s",
            (user_ids[manager_uname], user_ids[uname]),
        )

    # --- Campaign Goals (seeded before donations so donations can tag one) ---
    campaign_goals = [
        ("Monsoon Relief Drive 2026", 200000, today - timedelta(days=10), today + timedelta(days=50)),
        ("Winter Education Fund", 100000, today + timedelta(days=60), today + timedelta(days=150)),
    ]
    campaign_ids = {}
    for title, target, start, end in campaign_goals:
        cur.execute(
            "INSERT INTO campaign_goals (title, target_amount, start_date, end_date, created_by) VALUES (%s, %s, %s, %s, %s) RETURNING id",
            (title, target, start, end, user_ids["admin"]),
        )
        campaign_ids[title] = cur.fetchone()["id"]

    # --- Donations ---------------------------------------------------------
    donations = [
        ("priya.sharma", "Rakesh Gupta", "9812300001", 2500, "https://drive.google.com/file/d/demo1", "UTR2601010001", "approved", None, "Monsoon Relief Drive 2026"),
        ("priya.sharma", "Meena Kapoor", "9812300002", 6000, "https://drive.google.com/file/d/demo2", "UTR2601020002", "approved", None, "Monsoon Relief Drive 2026"),
        ("priya.sharma", "Vivek Singh", "9812300003", 1200, "https://drive.google.com/file/d/demo3", "UTR2601030003", "pending", None, None),
        ("rahul.verma", "Sunita Rao", "9812300004", 15000, "https://drive.google.com/file/d/demo4", "UTR2601040004", "approved", None, "Monsoon Relief Drive 2026"),
        ("rahul.verma", "Arjun Nair", "9812300005", 3000, "https://drive.google.com/file/d/demo5", "UTR2601050005", "rejected", "Blurry screenshot, please re-upload", None),
        ("ananya.das", "Deepak Joshi", "9812300006", 22000, "https://drive.google.com/file/d/demo6", "UTR2601060006", "approved", None, None),
        ("ananya.das", "Kavita Menon", "9812300007", 8500, "https://drive.google.com/file/d/demo7", "UTR2601070007", "approved", None, None),
        ("karan.mehta", "Nikhil Agarwal", "9812300008", 55000, "https://drive.google.com/file/d/demo8", "UTR2601080008", "approved", None, None),
        ("karan.mehta", "Pooja Bhatt", "9812300009", 4200, "https://drive.google.com/file/d/demo9", "UTR2601090009", "pending", None, None),
        ("sneha.iyer", "Manish Tiwari", "9812300010", 900, "https://drive.google.com/file/d/demo10", "UTR2601100010", "approved", None, None),
    ]
    for uname, donor, phone, amount, link, utr, status, note, campaign_title in donations:
        cur.execute(
            """INSERT INTO donations (user_id, donor_name, donor_phone, amount, drive_link, utr_reference, status, admin_note, reviewed_at, campaign_id)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (user_ids[uname], donor, phone, amount, link, utr, status, note,
             None if status == "pending" else today,
             campaign_ids.get(campaign_title) if campaign_title else None),
        )

    # --- Tasks ---------------------------------------------------------------
    tasks = [
        ("Share campaign post on Instagram", "Post the Bhumi monsoon-drive creative on your Instagram story and tag @bhumi.ngo.", today + timedelta(days=3)),
        ("Onboard 2 new donors", "Reach out to 2 potential donors from your network and log their contributions.", today + timedelta(days=7)),
        ("Attend weekly sync call", "Join the Sunday 6 PM Google Meet sync with your regional coordinator.", today + timedelta(days=2)),
        ("Submit weekly progress report", "Fill out the weekly Google Form with your outreach numbers.", today + timedelta(days=5)),
    ]
    task_ids = []
    for title, desc, deadline in tasks:
        cur.execute(
            "INSERT INTO tasks (title, description, deadline, created_by) VALUES (%s, %s, %s, %s) RETURNING id",
            (title, desc, deadline, user_ids["admin"]),
        )
        task_ids.append(cur.fetchone()['id'])

    # a couple of completions
    cur.execute("INSERT INTO task_completions (task_id, user_id) VALUES (%s, %s)", (task_ids[0], user_ids["priya.sharma"]))
    cur.execute("INSERT INTO task_completions (task_id, user_id) VALUES (%s, %s)", (task_ids[2], user_ids["karan.mehta"]))

    # --- Resources -------------------------------------------------------
    resources = [
        ("Bhumi Official Pitch Deck", "Pitch Deck", "https://drive.google.com/drive/folders/bhumi-pitch-deck"),
        ("Bhumi Logo Pack (PNG/SVG)", "Branding", "https://drive.google.com/drive/folders/bhumi-logo-pack"),
        ("Instagram Campaign Kit", "Social Media", "https://drive.google.com/drive/folders/bhumi-ig-kit"),
        ("WhatsApp Forward Templates", "Social Media", "https://drive.google.com/drive/folders/bhumi-whatsapp-kit"),
        ("Donor FAQ One-Pager", "Pitch Deck", "https://drive.google.com/drive/folders/bhumi-donor-faq"),
    ]
    for title, category, link in resources:
        cur.execute("INSERT INTO resources (title, category, link) VALUES (%s, %s, %s)", (title, category, link))

    # --- Announcements -----------------------------------------------------
    announcements = [
        ("Welcome to the new Bhumi Patna Portal!", "We've rebuilt the portal from the ground up — track your donations, missions, and rank all in one place. Reach out to your coordinator if anything looks off."),
        ("Monsoon Drive kicks off next week", "Get your outreach materials ready from the Resource Library. Top 5 fundraisers this month get a shoutout at the next all-hands call."),
    ]
    for title, message in announcements:
        cur.execute(
            "INSERT INTO announcements (title, message, created_by) VALUES (%s, %s, %s)",
            (title, message, user_ids["admin"]),
        )

    conn.commit()
    cur.close()
    conn.close()
    print("Database initialized and seeded successfully via Supabase!")
    print("Demo logins:")
    print("  admin            / Admin@123        (admin)")
    print("  admin.regional   / Admin@123        (admin, manages Priya/Rahul/Sneha)")
    print("  priya.sharma     / Intern@123       (intern)")
    print("  rahul.verma      / Intern@123       (intern)")
    print("  ananya.das       / Ambassador@123   (ambassador)")
    print("  karan.mehta      / Ambassador@123   (ambassador)")
    print("  sneha.iyer       / Intern@123       (intern)")


if __name__ == "__main__":
    import sys
    init_db(if_missing_only="--if-missing" in sys.argv)
