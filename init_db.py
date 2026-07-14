"""
Initializes bhumi.db from schema.sql and seeds it with a demo admin account,
a few intern/ambassador accounts, sample tasks, resources and donations.
Run this once before starting the app:  python init_db.py
"""
import os
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from datetime import date, timedelta
from werkzeug.security import generate_password_hash

DB_PATH = os.environ.get("DATABASE_PATH", os.path.join(os.path.dirname(__file__), "bhumi.db"))
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")


def init_db(if_missing_only=False):
    if os.path.exists(DB_PATH):
        if if_missing_only:
            print(f"Database already exists at {DB_PATH} — skipping re-seed.")
            return
        os.remove(DB_PATH)

    conn = psycopg2.connect(
    os.environ.get('postgresql://postgres:AdminBhumi%406458@db.tvpeifkivzonhguodour.supabase.co:5432/postgres'),
    cursor_factory=RealDictCursor
)
    with open(SCHEMA_PATH, "r") as f:
        conn.executescript(f.read())

    cur = conn.cursor()
    today = date.today()

    # --- Users -----------------------------------------------------------
    users = [
        # username, password, role, full_name, email, phone, tenure_start, tenure_end
        ("admin", "Admin@123", "admin", "Bhumi Admin", "admin@bhumi.ngo", "9999900000", None, None),
        ("priya.sharma", "Intern@123", "intern", "Priya Sharma", "priya@example.com", "9876500001",
         today - timedelta(days=20), today + timedelta(days=40)),
        ("rahul.verma", "Intern@123", "intern", "Rahul Verma", "rahul@example.com", "9876500002",
         today - timedelta(days=10), today + timedelta(days=50)),
        ("ananya.das", "Ambassador@123", "ambassador", "Ananya Das", "ananya@example.com", "9876500003",
         today - timedelta(days=35), today + timedelta(days=10)),
        ("karan.mehta", "Ambassador@123", "ambassador", "Karan Mehta", "karan@example.com", "9876500004",
         today - timedelta(days=5), today + timedelta(days=85)),
        ("sneha.iyer", "Intern@123", "intern", "Sneha Iyer", "sneha@example.com", "9876500005",
         today - timedelta(days=15), today + timedelta(days=2)),
    ]

    user_ids = {}
    for uname, pwd, role, name, email, phone, t_start, t_end in users:
        cur.execute(
            """INSERT INTO users (username, password_hash, role, full_name, email, phone, tenure_start, tenure_end)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (uname, generate_password_hash(pwd), role, name, email, phone, t_start, t_end),
        )
        user_ids[uname] = cur.lastrowid

    # --- Donations ---------------------------------------------------------
    donations = [
        ("priya.sharma", "Rakesh Gupta", 2500, "https://drive.google.com/file/d/demo1", "approved", None),
        ("priya.sharma", "Meena Kapoor", 6000, "https://drive.google.com/file/d/demo2", "approved", None),
        ("priya.sharma", "Vivek Singh", 1200, "https://drive.google.com/file/d/demo3", "pending", None),
        ("rahul.verma", "Sunita Rao", 15000, "https://drive.google.com/file/d/demo4", "approved", None),
        ("rahul.verma", "Arjun Nair", 3000, "https://drive.google.com/file/d/demo5", "rejected", "Blurry screenshot, please re-upload"),
        ("ananya.das", "Deepak Joshi", 22000, "https://drive.google.com/file/d/demo6", "approved", None),
        ("ananya.das", "Kavita Menon", 8500, "https://drive.google.com/file/d/demo7", "approved", None),
        ("karan.mehta", "Nikhil Agarwal", 55000, "https://drive.google.com/file/d/demo8", "approved", None),
        ("karan.mehta", "Pooja Bhatt", 4200, "https://drive.google.com/file/d/demo9", "pending", None),
        ("sneha.iyer", "Manish Tiwari", 900, "https://drive.google.com/file/d/demo10", "approved", None),
    ]
    for uname, donor, amount, link, status, note in donations:
        cur.execute(
            """INSERT INTO donations (user_id, donor_name, amount, drive_link, status, admin_note, reviewed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (user_ids[uname], donor, amount, link, status, note,
             None if status == "pending" else today),
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
            "INSERT INTO tasks (title, description, deadline, created_by) VALUES (?, ?, ?, ?)",
            (title, desc, deadline, user_ids["admin"]),
        )
        task_ids.append(cur.lastrowid)

    # a couple of completions
    cur.execute("INSERT INTO task_completions (task_id, user_id) VALUES (?, ?)", (task_ids[0], user_ids["priya.sharma"]))
    cur.execute("INSERT INTO task_completions (task_id, user_id) VALUES (?, ?)", (task_ids[2], user_ids["karan.mehta"]))

    # --- Resources -------------------------------------------------------
    resources = [
        ("Bhumi Official Pitch Deck", "Pitch Deck", "https://drive.google.com/drive/folders/bhumi-pitch-deck"),
        ("Bhumi Logo Pack (PNG/SVG)", "Branding", "https://drive.google.com/drive/folders/bhumi-logo-pack"),
        ("Instagram Campaign Kit", "Social Media", "https://drive.google.com/drive/folders/bhumi-ig-kit"),
        ("WhatsApp Forward Templates", "Social Media", "https://drive.google.com/drive/folders/bhumi-whatsapp-kit"),
        ("Donor FAQ One-Pager", "Pitch Deck", "https://drive.google.com/drive/folders/bhumi-donor-faq"),
    ]
    for title, category, link in resources:
        cur.execute("INSERT INTO resources (title, category, link) VALUES (?, ?, ?)", (title, category, link))

    conn.commit()
    conn.close()
    print(f"Database initialized at {DB_PATH}")
    print("Demo logins:")
    print("  admin            / Admin@123        (admin)")
    print("  priya.sharma     / Intern@123        (intern)")
    print("  rahul.verma      / Intern@123        (intern)")
    print("  ananya.das       / Ambassador@123    (ambassador)")
    print("  karan.mehta      / Ambassador@123    (ambassador)")
    print("  sneha.iyer       / Intern@123        (intern)")


if __name__ == "__main__":
    import sys
    init_db(if_missing_only="--if-missing" in sys.argv)
