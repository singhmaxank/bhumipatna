# Bhumi Patna Portal

A responsive web portal for Bhumi (bhumi.ngo) Interns and Campus Ambassadors to
track fundraising progress, log donations, and manage tasks — with a dedicated
Admin panel for financial verification, people management, and oversight.

Built with **Flask + PostgreSQL (Supabase)** on the backend, **Tailwind CSS**
on the frontend, and served in production by **Gunicorn**.

---

## 1. Features

### Security & access control
- Passwords are hashed with Werkzeug's `generate_password_hash` / `check_password_hash` — never stored in plaintext.
- Every database query uses parameterized `%s` placeholders via `psycopg2` — no string-concatenated SQL anywhere, so the app is not vulnerable to SQL injection.
- Role-based routing: `admin` accounts land on `/admin`; `intern`/`ambassador` accounts land on `/dashboard`. Every route is protected with `@login_required` / `@role_required` decorators, so a volunteer can't reach admin-only endpoints even by guessing the URL.
- Self-service **Forgot password** flow: a user verifies their identity with their username and the email on file, then sets a new password directly. The verification only stays valid for 10 minutes and is cleared as soon as it's used.

### Intern / Campus Ambassador dashboard (`/dashboard`)
- Live tenure countdown (days / hours / minutes / seconds), computed client-side from the account's tenure end-date.
- Donation submission form: donor name, amount, and a Google Drive verification link.
- Automatic rank tiers — **Bronze / Silver / Gold / Platinum** — based on **verified (approved)** donation totals, with a progress meter showing how much more is needed for the next tier.
- Org-wide Top 5 leaderboard.
- Missions log with a "mark complete" button per task.
- Resource library of pitch decks, branding assets, and social media kits.

### Admin panel (`/admin`)
- **Verification Hub** — approve or reject every submitted donation with one click. Rejecting requires a feedback note (e.g. "Blurry image link"), which immediately shows up on that volunteer's own dashboard.
- **Interns** and **Campus Ambassadors** — separate tabs to create, edit, and delete accounts for each role, including resetting a volunteer's password by hand and updating their tenure dates.
- **Missions** — publish, edit, and delete tasks assigned to all volunteers.
- **Resources** — add, edit, and delete resource-library links.
- **Leaderboard** — the full org-wide ranking, visible to admins as well as volunteers.
- One-click CSV export of the full donation ledger (`/admin/export.csv`).

### Design
A simple, minimal interface: one typeface (Inter) throughout, a light neutral
background, flat cards with thin borders, and a single accent color — no
heavy textures, gradients, or mixed display fonts.

---

## 2. Project structure

```
bhumi_portal/
├── app.py                    # Routes, auth, business logic
├── schema.sql                 # PostgreSQL schema
├── init_db.py                 # DB init + demo seed data (--if-missing flag supported)
├── requirements.txt            # Flask, Werkzeug, gunicorn, psycopg2-binary
├── runtime.txt                 # Pinned Python version for hosting platforms
├── Procfile                    # Process declaration read by Render/Heroku-style platforms
├── render.yaml                  # Render Blueprint (one-click infra-as-code deploy)
├── templates/
│   ├── base.html                # Shared layout, nav, flash messages
│   ├── login.html
│   ├── forgot_password.html
│   ├── reset_password.html
│   ├── intern_dashboard.html
│   └── admin_dashboard.html
└── static/
    ├── css/style.css            # Minimal design system (colors, type, components)
    └── img/bhumi_logo.png
```

---

## 3. Running it locally

This app expects a PostgreSQL database — a free [Supabase](https://supabase.com)
project works well. Grab your project's connection string (Project Settings →
Database → Connection string → URI) and use it as `DATABASE_URL` below.

```bash
cd bhumi_portal
pip install -r requirements.txt

export DATABASE_URL="postgresql://postgres:<password>@<host>:5432/postgres"
export BHUMI_SECRET_KEY="some-long-random-string"

# Creates tables and seeds demo accounts + sample data.
# Re-running this (without --if-missing) wipes and recreates the tables.
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

### Step 0 — push a clean copy of this project to GitHub
1. Delete everything in your repo (or start a brand-new repo).
2. Copy in every file from this project, including the "dot" files (`Procfile`, `runtime.txt`).
3. `git add -A && git commit -m "Bhumi Patna Portal — clean deploy" && git push`
4. Verify on GitHub's website that `requirements.txt`, `Procfile`, and `render.yaml` are visible at the repo root.

### Deploy
1. Create a PostgreSQL database (Supabase is the easiest free option) and copy its connection string.
2. In Render: **New → Blueprint**, point it at your repo. It reads `render.yaml`, provisions the web service, and generates `BHUMI_SECRET_KEY` automatically.
3. In the Render dashboard, set the `DATABASE_URL` environment variable to your Supabase/PostgreSQL connection string (this is intentionally left blank in `render.yaml` since it's a secret).
4. Deploy. Once the service is live, run `python init_db.py` once (Render Shell, or locally against the same `DATABASE_URL`) to create tables and seed demo data.
5. Visit your `https://your-app.onrender.com` URL.

If you're not using the Blueprint flow, configure manually:
- **Build Command:** `pip install --upgrade pip && pip install -r requirements.txt`
- **Start Command:** `python -m gunicorn app:app --bind 0.0.0.0:$PORT`
- Environment variables: `DATABASE_URL`, `BHUMI_SECRET_KEY`

**Note on `gunicorn: command not found`:** the start command uses
`python -m gunicorn ...` instead of bare `gunicorn ...`, which bypasses PATH
lookup issues some hosts run into.

**Note on `No open ports detected`:** Render assigns a random port via `$PORT`
— the app must bind to `0.0.0.0:$PORT`, which `--bind 0.0.0.0:$PORT` already does.

---

## 5. Notes for production hardening

- `BHUMI_SECRET_KEY` must be a long, random, secret value in production — never reuse the development fallback in `app.py`.
- Make sure every volunteer account has an email on file if you want them to be able to use "Forgot password" — otherwise an admin has to reset their password manually from the Interns / Campus Ambassadors tab.
- Ensure the app is only ever served over HTTPS in production (Render provides this automatically on `onrender.com` domains and custom domains with a certificate).
- Rotate the demo account passwords listed above before letting anyone but you access the deployed instance.
