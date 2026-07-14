# Bhumi Volunteer Portal

A responsive web portal for Bhumi (bhumi.ngo) Interns and Campus Ambassadors to
track fundraising progress, log donations, and manage tasks — with a dedicated
Admin panel for financial verification and oversight.

Built with **Flask + SQLite** on the backend and **Tailwind CSS** on the frontend.

## Features

**Security**
- Passwords are hashed with Werkzeug's `generate_password_hash` / `check_password_hash` (never stored in plaintext).
- All database access uses parameterized queries (`?` placeholders) — no string-concatenated SQL anywhere, so the app is not vulnerable to SQL injection.
- Role-based routing: `admin` accounts land on `/admin`, `intern`/`ambassador` accounts land on `/dashboard`. Routes are protected with `@role_required` decorators.

**Intern / Campus Ambassador dashboard** (`/dashboard`)
- Live tenure countdown (days / hours / minutes / seconds) computed client-side from the account's tenure end-date.
- Donation submission form (donor name, amount, Google Drive verification link).
- Automatic rank tiers — Bronze / Silver / Gold / Platinum — based on **verified (approved)** donation totals, with a progress meter showing how much is needed for the next tier.
- Org-wide Top 5 leaderboard.
- Missions log with a "mark complete" action per task.
- Resource library of pitch decks, branding assets and social kits.

**Admin panel** (`/admin`)
- Financial Verification Hub: approve or reject every submitted donation.
- Rejecting a donation requires a feedback note (e.g. "Blurry image link"), which immediately shows up on that volunteer's dashboard.
- One-click CSV export of the full donation ledger (`/admin/export.csv`).
- Forms to provision new intern/ambassador accounts (with tenure dates), publish new missions, and add new resource-library links.

## Getting started

```bash
cd bhumi_portal
pip install -r requirements.txt

# Creates bhumi.db and seeds demo accounts + sample data.
# Re-running this wipes and recreates the database.
python init_db.py

python app.py
```

The app runs at `http://127.0.0.1:5000`.

## Demo logins

| Username | Password | Role |
|---|---|---|
| admin | Admin@123 | Admin |
| priya.sharma | Intern@123 | Intern |
| rahul.verma | Intern@123 | Intern |
| ananya.das | Ambassador@123 | Campus Ambassador |
| karan.mehta | Ambassador@123 | Campus Ambassador |
| sneha.iyer | Intern@123 | Intern |

**Change these before deploying anywhere real.** Also set a strong, random
`BHUMI_SECRET_KEY` environment variable in production (the app falls back to
a development key otherwise).

## Project structure

```
bhumi_portal/
├── app.py                 # Routes, auth, business logic
├── schema.sql              # SQLite schema
├── init_db.py              # DB init + demo seed data
├── requirements.txt
├── bhumi.db                 # SQLite database (created by init_db.py)
├── templates/
│   ├── base.html            # Shared layout, nav, flash messages
│   ├── login.html
│   ├── intern_dashboard.html
│   └── admin_dashboard.html
└── static/
    ├── css/style.css        # Brand design system (colors, ledger/stamp motifs)
    └── img/bhumi_logo.png
```

## Rank tier thresholds (verified donations, INR)

| Tier | Range |
|---|---|
| Bronze | ₹0 – ₹4,999 |
| Silver | ₹5,000 – ₹14,999 |
| Gold | ₹15,000 – ₹49,999 |
| Platinum | ₹50,000+ |

These thresholds live in `RANK_TIERS` at the top of `app.py` — adjust freely.

## Deploying to Render

**Important:** Render's free web services have an *ephemeral* filesystem — any
file written locally (including the `bhumi.db` SQLite file) is wiped every
time the service redeploys, restarts, or spins down from inactivity. Pick one
of the two paths below depending on whether you need the data to stick around.

### Option A — Quick demo (free, data resets periodically)
Fine for showing someone a live link; not fine for real donation records.

1. Push this project to a GitHub repo.
2. In the Render dashboard: **New > Web Service** → connect the repo.
3. Set:
   - **Build Command:** `pip install -r requirements.txt && python init_db.py --if-missing`
   - **Start Command:** `gunicorn app:app`
   - **Instance Type:** Free
4. Add an environment variable `BHUMI_SECRET_KEY` set to a long random string.
5. Deploy. You'll get a live `https://your-app.onrender.com` URL.
6. Know the trade-off: every redeploy/restart re-runs the build command, and since there's no persistent disk on the free tier, `init_db.py` will recreate the database with fresh demo data each time it's missing.

### Option B — Real usage (small paid cost, data persists)
1. Push to GitHub as above.
2. Easiest: commit the included `render.yaml` to your repo root, then in Render choose **New > Blueprint** and point it at your repo. It provisions the web service, a 1GB persistent disk mounted at `/var/data`, and generates `BHUMI_SECRET_KEY` for you automatically.
3. Or configure manually in the dashboard:
   - **Build Command:** `pip install -r requirements.txt && python init_db.py --if-missing`
   - **Start Command:** `gunicorn app:app`
   - **Instance Type:** Starter (or higher — persistent disks require a paid plan)
   - Add a **Disk**: mount path `/var/data`, size 1GB
   - Environment variable `DATABASE_PATH` = `/var/data/bhumi.db`
   - Environment variable `BHUMI_SECRET_KEY` = a long random string
4. Deploy. The database now lives on the persistent disk, so donation and user records survive restarts and redeploys.

Either way, the free instance type also spins down after ~15 minutes of no
traffic and takes 30–60 seconds to wake back up on the next request — expected
free-tier behavior, not a bug. If that cold start is a problem for real users,
that's another reason to move to a paid instance type.

**Longer term:** if you outgrow SQLite (heavier concurrent write traffic),
Render's managed Postgres is the natural next step, but that needs a code
change (swapping `sqlite3` for `psycopg2`/`SQLAlchemy`) — happy to help with
that migration when you're ready for it.

## Notes for production deployment

- Swap the Flask dev server for a production WSGI server (gunicorn/uwsgi) behind a reverse proxy.
- Set `BHUMI_SECRET_KEY` to a long random value via environment variable.
- Consider moving from SQLite to PostgreSQL/MySQL if concurrent write volume grows.
- Add HTTPS (via your reverse proxy / hosting provider) — cookies here are session-based and should be sent over TLS only in production.
