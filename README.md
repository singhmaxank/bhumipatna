# Bhumi Volunteer Portal

A responsive web portal for Bhumi (bhumi.ngo) Interns and Campus Ambassadors to
track fundraising progress, log donations, and manage tasks — with a dedicated
Admin panel for financial verification and oversight.

Built with **Flask + SQLite** on the backend, **Tailwind CSS** on the frontend,
and served in production by **Gunicorn**.

---

## 1. Features

### Security & access control
- Passwords are hashed with Werkzeug's `generate_password_hash` / `check_password_hash` — never stored in plaintext.
- Every database query uses parameterized `?` placeholders — no string-concatenated SQL anywhere, so the app is not vulnerable to SQL injection.
- Role-based routing: `admin` accounts land on `/admin`; `intern`/`ambassador` accounts land on `/dashboard`. Every route is protected with `@login_required` / `@role_required` decorators, so a volunteer can't reach admin-only endpoints even by guessing the URL.

### Intern / Campus Ambassador dashboard (`/dashboard`)
- Live tenure countdown (days / hours / minutes / seconds), computed client-side from the account's tenure end-date.
- Donation submission form: donor name, amount, and a Google Drive verification link.
- Automatic rank tiers — **Bronze / Silver / Gold / Platinum** — based on **verified (approved)** donation totals, with a progress meter showing how much more is needed for the next tier.
- Org-wide Top 5 leaderboard.
- Missions log with a "mark complete" button per task.
- Resource library of pitch decks, branding assets, and social media kits.

### Admin panel (`/admin`)
- Financial Verification Hub: approve or reject every submitted donation with one click.
- Rejecting a donation requires a feedback note (e.g. "Blurry image link"), which immediately shows up on that volunteer's own dashboard.
- One-click CSV export of the full donation ledger (`/admin/export.csv`).
- Forms to provision new intern/ambassador accounts (with tenure start/end dates), publish new missions, and add new resource-library links.

---

## 2. Project structure

```
bhumi_portal/
├── app.py                    # Routes, auth, business logic
├── schema.sql                 # SQLite schema
├── init_db.py                 # DB init + demo seed data (--if-missing flag supported)
├── requirements.txt            # Flask, Werkzeug, gunicorn
├── runtime.txt                 # Pinned Python version for hosting platforms
├── Procfile                    # Process declaration read by Render/Heroku-style platforms
├── render.yaml                  # Render Blueprint (one-click infra-as-code deploy)
├── bhumi.db                    # SQLite database (created by init_db.py)
├── templates/
│   ├── base.html                # Shared layout, nav, flash messages
│   ├── login.html
│   ├── intern_dashboard.html
│   └── admin_dashboard.html
└── static/
    ├── css/style.css            # Brand design system (colors, ledger/stamp motifs)
    └── img/bhumi_logo.png
```

---

## 3. Running it locally

```bash
cd bhumi_portal
pip install -r requirements.txt

# Creates bhumi.db and seeds demo accounts + sample data.
# Re-running this (without --if-missing) wipes and recreates the database.
python init_db.py

python app.py
```

The app runs at `http://127.0.0.1:5000` using Flask's built-in dev server
(fine for local testing; Render uses gunicorn instead — see below).

### Demo logins

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

### Rank tier thresholds (verified donations, INR)

| Tier | Range |
|---|---|
| Bronze | ₹0 – ₹4,999 |
| Silver | ₹5,000 – ₹14,999 |
| Gold | ₹15,000 – ₹49,999 |
| Platinum | ₹50,000+ |

These live in `RANK_TIERS` at the top of `app.py` — adjust freely.

---

## 4. Deploying to Render

**Important — read this first:** Render's *free* web services have an
**ephemeral filesystem**. Any file written locally — including the `bhumi.db`
SQLite file — is wiped every time the service redeploys, restarts, or spins
down from inactivity. Pick Option A or B below depending on whether you need
donation/user data to actually stick around.

### Step 0 — push a clean copy of this project to GitHub
Don't merge these files into an existing, possibly-stale repo. Best practice:
1. Delete everything in your repo (or start a brand-new repo).
2. Copy in every file from this project, including the "dot" files (`Procfile`, `runtime.txt`) — these don't show up in some file managers by default, so double check they're actually there.
3. `git add -A && git commit -m "Bhumi portal — clean deploy" && git push`
4. **Verify on GitHub's website** (not just locally) that `requirements.txt`, `Procfile`, and `render.yaml` are all visible in the repo at the root. If Render can't see a file on GitHub, it can't use it — this step has been the source of every error so far.

### Option A — Quick demo (free, data resets periodically)
Fine for sharing a live link; not fine for real donation records.

1. In the Render dashboard: **New → Web Service** → connect your repo.
2. Set:
   - **Build Command:** `pip install --upgrade pip && pip install -r requirements.txt && python init_db.py --if-missing`
   - **Start Command:** `python -m gunicorn app:app --bind 0.0.0.0:$PORT`
   - **Instance Type:** Free
3. Add environment variable `BHUMI_SECRET_KEY` = a long random string.
4. Deploy. You'll get a live `https://your-app.onrender.com` URL.
5. Know the trade-off: since there's no persistent disk on the free tier, `init_db.py --if-missing` recreates the database with fresh demo data every time the previous one gets wiped.

### Option B — Real usage (small paid cost, data persists)
1. Commit the included `render.yaml` to your repo root (already done in this project).
2. In Render: **New → Blueprint**, point it at your repo. It provisions the web service, a 1GB persistent disk mounted at `/var/data`, and generates `BHUMI_SECRET_KEY` automatically.
3. Or configure manually:
   - **Build Command:** `pip install --upgrade pip && pip install -r requirements.txt && python init_db.py --if-missing`
   - **Start Command:** `python -m gunicorn app:app --bind 0.0.0.0:$PORT`
   - **Instance Type:** Starter or higher (persistent disks require a paid plan)
   - Add a **Disk**: mount path `/var/data`, size 1GB
   - Environment variable `DATABASE_PATH` = `/var/data/bhumi.db`
   - Environment variable `BHUMI_SECRET_KEY` = a long random string
4. Deploy. The database now lives on the persistent disk, so records survive restarts and redeploys.

Either way, the **free** instance type also spins down after ~15 minutes of no
traffic and takes 30–60 seconds to wake back up on the next request — this is
expected Render behavior, not a bug.

**Longer term:** if you outgrow SQLite (heavier concurrent write traffic),
Render's managed Postgres is the natural next step, but that needs a code
change (swapping `sqlite3` for `psycopg2`/`SQLAlchemy`).

---

## 5. Troubleshooting (errors already seen while deploying this project)

### `bash: line 1: gunicorn: command not found`
This means the `gunicorn` executable isn't resolvable on Render's `$PATH` at
start-time — even when it's correctly installed by pip during the build.
This has been fixed in this project two ways, both already applied:
1. The start command uses **`python -m gunicorn ...`** instead of bare `gunicorn ...`. Invoking gunicorn as a Python module bypasses PATH lookup entirely and finds it directly via the same Python environment pip installed it into — this is the fix that actually resolves the error, not just a workaround.
2. `requirements.txt` and the build command both explicitly install/upgrade pip and gunicorn, so there's no ambiguity about it being present.

If you still see this error after using `python -m gunicorn app:app --bind 0.0.0.0:$PORT` as your Start Command:
- Open your repo's `requirements.txt` **on github.com directly** and confirm you can see `gunicorn==22.0.0` in the file, in the actual repo Render is building from.
- Check **Settings → Root Directory** on the Render service — if it's set to a subfolder that doesn't match where your files actually live in the repo, Render will build/run from the wrong place.
- Check **Settings → Branch** — confirm it matches the branch you actually pushed to.
- Use **Manual Deploy → Clear build cache & deploy** — a stale cached build layer can mask a fix that's already in your repo.
- In the build log, confirm you see a line like `Installing collected packages: ... gunicorn` — if that line is missing, the build genuinely isn't installing it, which points back to the `requirements.txt` content/location issue above.

### `No open ports detected` / `Docs on specifying a port`
Gunicorn was running but not listening on the port Render expects. Render
assigns a random port via the `$PORT` environment variable, and your app must
bind to `0.0.0.0:$PORT`, not a hardcoded port. Fixed by including
`--bind 0.0.0.0:$PORT` directly in the Start Command (already applied here).

### Deploy shows "Build successful" but the previous deploy's error repeats
This happens when the dashboard's Start Command field and what's actually in
the repo (`Procfile` / `render.yaml`) disagree, or when a manual dashboard
override is stale. Since this project declares the start command in three
places (dashboard field you set, `Procfile`, and `render.yaml`), make sure all
three agree if you're not using the Blueprint flow — the safest option is to
use **New → Blueprint** with `render.yaml` so there's only one source of truth.

---

## 6. Notes for production hardening

- `BHUMI_SECRET_KEY` must be a long, random, secret value in production — never reuse the development fallback in `app.py`.
- Consider moving from SQLite to PostgreSQL if concurrent write volume grows (Render offers managed Postgres).
- Ensure the app is only ever served over HTTPS in production (Render provides this automatically on `onrender.com` domains and custom domains with a certificate).
- Rotate the demo account passwords listed above before letting anyone but you access the deployed instance.
