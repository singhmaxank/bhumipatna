# Bhumi Patna Portal

A responsive web portal for Bhumi Patna interns and Campus Ambassadors to
track fundraising progress, log donations, and manage tasks — with a full
Admin panel for financial verification, account management, and oversight.

Built with **Flask + PostgreSQL (Supabase)** on the backend, a minimal
**Tailwind CSS** design on the frontend, and served in production by
**Gunicorn**.

---

## 1. Features

### Design
- Modern visual system: **Manrope** (display/headings) paired with **Inter** (body text), a signature "flame gradient" (leaf green → marigold → gold, echoing the logo's torch mark) used consistently across progress bars, chart accents, and card highlights.
- **Dark mode** — a toggle in the nav (and on the login screen) switches themes instantly and remembers your preference across visits (stored locally in your browser).
- **Loading splash screen** — visiting the site's root URL shows a branded loading screen (Bhumi logo + animated progress bar) for about 1.5 seconds before continuing on to the login page (or straight to your dashboard if you're already logged in).
- Toast-style notifications instead of static banners — success/error messages slide in, then auto-dismiss.
- Avatar initials with deterministic per-person colors, used throughout the nav, leaderboard, and admin lists.
- Fully responsive: stacks cleanly on mobile, expands to multi-column layouts on desktop.

### Progressive Web App & push notifications
- The portal is installable as a PWA (via the browser's "Install app" / "Add to Home Screen" prompt) thanks to `manifest.json` and a service worker (`/sw.js`).
- A bell icon in the nav lets any logged-in user opt in to browser push notifications (this is a user-initiated action — the app never auto-requests permission on load, since browsers often block or ignore that).
- Once subscribed, notifications go out automatically for:
  - **New announcements and new missions** → pushed to every intern/ambassador.
  - **A new donation submitted for approval** → pushed to every admin.
  - **A donation getting approved (or rejected)** → pushed to the volunteer who submitted it.
- Push delivery uses the standard Web Push protocol (VAPID) via the `pywebpush` library. A working key pair ships as a default so this works out of the box; see the Troubleshooting section for how to generate your own for production.
- Delivery failures (e.g. a stale/expired subscription, or a network hiccup) are caught and logged — they never break the action that triggered them, so donation submission/approval always succeeds even if a notification can't be delivered.

### Security & access control
- Passwords are hashed with Werkzeug's `generate_password_hash` / `check_password_hash` — never stored in plaintext.
- Every database query uses parameterized `%s` placeholders via `psycopg2` — no string-concatenated SQL anywhere, so the app is not vulnerable to SQL injection.
- Role-based routing: `admin` accounts land on `/admin`; `intern`/`ambassador` accounts land on `/dashboard`. Every route is protected with `@login_required` / `@role_required` decorators, so a volunteer can't reach admin-only endpoints even by guessing the URL.
- The login page has a show/hide toggle (eye icon) on the password field.
- **Forgot password:** clicking "Forgot your password?" on the login page opens a popup explaining that password resets go through your program admin/team head, who can set a new password for you from the Admin Panel's Edit option. This is intentionally not self-service — resets are admin-mediated for security.
- **My Profile / self-service password change** (`/profile`): every logged-in user — volunteer or admin — can view their own account details and change their own password (requires entering the current password first), without needing an admin to do it for them.

### Intern / Campus Ambassador dashboard (`/dashboard`)
- **Announcements banner** — admins can post org-wide notices that show up right at the top of every volunteer's dashboard.
- Live tenure countdown (days / hours / minutes / seconds), computed client-side from the account's tenure end-date.
- **Donation submission form:** Name, Phone Number, Amount (INR), Screenshot Link (Google Drive), UTR/Transaction ID, and an optional **Campaign** selector — tag a donation to a specific campaign goal and it counts toward that campaign's progress bar once approved. Leave it blank if the donation isn't for any particular campaign.
- **Campaign Goals tab** — see every campaign with a live progress bar (verified, campaign-tagged donations raised vs. target).
- Automatic rank tiers — **Bronze / Silver / Gold / Platinum** — based on **verified (approved)** donation totals, with a progress meter showing how much more is needed for the next tier.
- Org-wide Top 5 leaderboard, with avatars.
- Missions log with a "mark complete" button per task — **overdue missions are flagged automatically** if the deadline has passed and it's still incomplete.
- Resource library of pitch decks, branding assets, and social media kits, with a **live search box** to filter by title or category.

### Admin panel (`/admin`)
- **Admin hierarchy:** the org can have multiple admin accounts (typically 8-10 for a chapter this size), each able to manage a subset of interns/ambassadors. Every intern/ambassador can be assigned to a managing admin (during account creation or from Edit), and the Interns/Campus Ambassadors lists can be filtered by manager. Any admin can still see and act on the full org's data — this is an organizational assignment, not a hard access restriction, so every admin retains full visibility.
- **Admins tab:** admins can create new admin accounts, and edit any admin's details/password. A safety check prevents deleting your own account or the last remaining admin, so the portal can never be locked out of admin access.
- **Verification Hub:** approve or reject every submitted donation with one click. Rejecting requires a feedback note (e.g. "Blurry image link"), which immediately shows up on that volunteer's own dashboard. **Search by donor or volunteer name, and filter by status**, all live/client-side, with **pagination** (8 per page).
- **Interns** and **Campus Ambassadors** are two separate sections, each with its own account-creation form, its own searchable + **paginated** list (6 per page), and inline **Edit** (name, email, phone, tenure dates, and optionally a new password) / **Delete** (with a confirmation prompt) per row.
- **Missions:** create, edit, and delete any mission from the same screen — overdue ones are flagged.
- **Resources:** create, edit, and delete any resource-library link from the same screen.
- **Campaign Goals:** create, edit, and delete fundraising campaigns (title, target amount, optional start/end dates for display purposes). Each campaign's progress bar is driven by donations volunteers explicitly tag to it (see the donation form above) — not just anything submitted during its date window.
- **Announcements:** post and delete org-wide notices that appear on every volunteer's dashboard.
- **Leaderboard:** the same org-wide ranking volunteers see, also available to admins for oversight.
- **PDF export** of the donation ledger (`/admin/export.pdf`), with an optional start/end date filter — leave both blank for an all-time export. Includes donor name, phone, amount, UTR/transaction ID, and status for every matching entry, plus a summary of totals.

> **Note on deleting a user:** removing an intern/ambassador account also removes their donation history and mission-completion records, since those rows reference the account. You'll get a confirmation prompt before this happens. Admin accounts can't be deleted from this screen.

### Footer
Every page's footer links to the main Bhumi site, Terms of Service, Privacy
Policy, Legal, and Bhumi Care, alongside the "Change doesn't wait, & neither
should you!" credit line.

---

## 2. Project structure

```
bhumipatna-main/
├── app.py                     # Routes, auth, business logic (PostgreSQL via psycopg2)
├── schema.sql                  # PostgreSQL schema (safe to re-run — uses IF NOT EXISTS / ADD COLUMN IF NOT EXISTS)
├── init_db.py                  # DB init + demo seed data (--if-missing flag supported)
├── requirements.txt             # Flask, Werkzeug, gunicorn, psycopg2-binary, reportlab, pywebpush
├── .python-version               # Pins the Python version Render actually uses (runtime.txt is deprecated)
├── Procfile                     # Process declaration read by Render/Heroku-style platforms
├── render.yaml                   # Render Blueprint (one-click infra-as-code deploy)
├── templates/
│   ├── base.html                 # Shared layout, nav, dark mode + toast + push-subscription scripts
│   ├── splash.html                 # Loading screen shown at the root URL
│   ├── login.html                 # Show/hide password toggle + "contact your admin" forgot-password modal
│   ├── profile.html                # Self-service account view + password change
│   ├── intern_dashboard.html
│   ├── admin_dashboard.html          # Includes search/filter/pagination, Admins tab, Campaign Goals tab
│   ├── _user_fields.html          # Shared form fields for creating a volunteer account
│   └── _user_row.html             # Shared row partial (edit/delete) for Interns & Campus Ambassadors
└── static/
    ├── css/style.css              # Modern design system: Manrope+Inter, dark mode, flame-gradient signature
    ├── manifest.json                # PWA manifest (installability)
    ├── sw.js                        # Service worker (push notifications + basic app-shell caching)
    └── img/bhumi_logo.png
```

Two external CDNs are loaded in the templates: Google Fonts (Manrope/Inter) and
`cdn.tailwindcss.com` for utility classes. These need normal outbound internet
access to load — if you're testing behind a restrictive firewall/proxy that
blocks these domains, the page will fall back to unstyled HTML (see
Troubleshooting).

---

## 3. Database setup (Supabase / PostgreSQL)

1. Create a project at [supabase.com](https://supabase.com) (or use any PostgreSQL instance).
2. In Supabase: **Project Settings → Database → Connection string** — copy the URI (the "Connection pooling" URI is generally the right one for a web app like this).
3. Set it as an environment variable:
   ```bash
   export DATABASE_URL="postgresql://postgres:[YOUR-PASSWORD]@[YOUR-HOST]:5432/postgres"
   ```
4. Initialize and seed the database:
   ```bash
   pip install -r requirements.txt
   python init_db.py            # first run: creates tables + demo data
   python init_db.py --if-missing   # safe to re-run any time — skips seeding if data already exists
   ```

**Important:** always use `--if-missing` in any automated build step (like Render's build command). Without it, `init_db.py` re-seeds unconditionally, which will crash with a duplicate-key error the second time it runs against a database that already has data in it.

**Upgrading an existing deployment:** if you already had this app running against
a Supabase database from an earlier version (before donor phone/UTR fields or
Campaign Goals existed), you don't need to do anything special — `schema.sql`
uses `CREATE TABLE IF NOT EXISTS` and `ADD COLUMN IF NOT EXISTS` throughout, so
every deploy safely patches your existing database with any new tables/columns
without touching your existing data. This has been tested against a database
seeded with the older schema to confirm no data loss.

---

## 4. Running it locally

```bash
export DATABASE_URL="postgresql://...your Supabase connection string..."
export BHUMI_SECRET_KEY="some-long-random-string"

pip install -r requirements.txt
python init_db.py --if-missing
python app.py
```

The app runs at `http://127.0.0.1:5000` using Flask's built-in dev server
(fine for local testing; production uses gunicorn — see below).

### Demo logins

| Username | Password | Role |
|---|---|---|
| admin | Admin@123 | Admin |
| admin.regional | Admin@123 | Admin (manages Priya, Rahul, Sneha) |
| priya.sharma | Intern@123 | Intern |
| rahul.verma | Intern@123 | Intern |
| ananya.das | Ambassador@123 | Campus Ambassador |
| karan.mehta | Ambassador@123 | Campus Ambassador |
| sneha.iyer | Intern@123 | Intern |

**Change these before letting anyone but you access the deployed instance.**
Also set a strong, random `BHUMI_SECRET_KEY` — the app falls back to an
insecure development key if this isn't set.

### Rank tier thresholds (verified donations, INR)

| Tier | Range |
|---|---|
| Bronze | ₹0 – ₹4,999 |
| Silver | ₹5,000 – ₹14,999 |
| Gold | ₹15,000 – ₹49,999 |
| Platinum | ₹50,000+ |

These live in `RANK_TIERS` at the top of `app.py` — adjust freely.

---

## 5. Deploying to Render

Since the database now lives on Supabase (not on Render's own disk), Render's
**free** instance type works fine — there's no need for a paid persistent
disk anymore.

### Step 0 — push a clean copy of this project to GitHub
Replace your repo's contents entirely rather than merging file-by-file, and
make sure "dot" files (`Procfile`, `runtime.txt`) actually make it into the
repo — some file managers hide them by default.

### Step 1 — create the web service
1. In Render: **New → Web Service** → connect your repo (or **New → Blueprint** to use the included `render.yaml` directly).
2. If configuring manually, set:
   - **Build Command:** `pip install --upgrade pip && pip install -r requirements.txt && python init_db.py --if-missing`
   - **Start Command:** `python -m gunicorn app:app --bind 0.0.0.0:$PORT`
   - **Instance Type:** Free (or higher, if you want it to stay warm — see below)
3. Add environment variables:
   - `DATABASE_URL` = your Supabase connection string
   - `BHUMI_SECRET_KEY` = a long random string
   - `PYTHON_VERSION` = `3.12.7` (recommended — see the Troubleshooting section below on why this matters for `psycopg2-binary`)
   - `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_CLAIM_EMAIL` — optional but recommended for push notifications; see "Generating your own VAPID keys" below.
4. Deploy. You'll get a live `https://your-app.onrender.com` URL.

The free instance type spins down after ~15 minutes of no traffic and takes
30–60 seconds to wake back up on the next request — this is expected Render
behavior, not a bug. Upgrade to a paid instance type if you need it to stay
warm.

### Generating your own VAPID keys (for push notifications)

The app ships with a working default VAPID key pair so push notifications
work immediately — but that key pair is public (it's in this repo's source),
so anyone could technically use it to send push messages claiming to be your
app. For a real deployment, generate your own pair:

```bash
pip install py_vapid pywebpush
python3 - <<'EOF'
from py_vapid import Vapid02
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
import base64

vapid = Vapid02()
vapid.generate_keys()

priv_value = vapid.private_key.private_numbers().private_value
private_b64 = base64.urlsafe_b64encode(priv_value.to_bytes(32, 'big')).rstrip(b'=').decode()

raw_public = vapid.public_key.public_bytes(encoding=Encoding.X962, format=PublicFormat.UncompressedPoint)
public_b64 = base64.urlsafe_b64encode(raw_public).rstrip(b'=').decode()

print("VAPID_PUBLIC_KEY =", public_b64)
print("VAPID_PRIVATE_KEY =", private_b64)
EOF
```

Set the two printed values as `VAPID_PUBLIC_KEY` and `VAPID_PRIVATE_KEY`
environment variables in Render, plus `VAPID_CLAIM_EMAIL` (a `mailto:` address
identifying your app to push services — any real contact address works).
**If you change these on an existing deployment, everyone's existing push
subscriptions become invalid** (the browser ties a subscription to the
specific public key it was created with) — anyone who'd already tapped the
bell icon will need to tap it again to resubscribe.

---

## 6. Troubleshooting

### `Push notification failed: WebPushException ... Host not in allowlist` / notifications don't arrive
If you're testing inside a sandboxed environment or behind a restrictive
firewall/proxy, outbound requests to browser push services (e.g.
`fcm.googleapis.com` for Chrome, Mozilla's push service for Firefox) may be
blocked. This has no effect on the rest of the app — donation submission,
approval, announcements, and missions all still work normally, since push
delivery failures are caught and logged rather than allowed to break the
request. On a normal server with normal internet access (including Render),
this isn't an issue.

### `psycopg2.OperationalError: connection to server at "db.<project>.supabase.co" ... Network is unreachable`
This means `DATABASE_URL` is set, but it's using Supabase's **direct**
connection string, which resolves to an IPv6-only address. Render's outbound
network doesn't support IPv6, so the connection fails — this is a networking
mismatch, not a credentials problem. Fix:
1. In Supabase: your project → **Connect** (top of the dashboard) → copy the **Session pooler** or **Transaction pooler** connection string instead of the direct one. It looks like:
   ```
   postgresql://postgres.<your-project-ref>:[YOUR-PASSWORD]@aws-0-<region>.pooler.supabase.com:5432/postgres
   ```
   (Note the username becomes `postgres.<project-ref>` for the pooler — that's expected, not a typo.)
2. In Render → **Environment**, replace `DATABASE_URL` with this pooler string.
3. Redeploy.

The pooler (Supavisor) is IPv4-compatible on every Supabase project tier, so
this works regardless of plan.

### `psycopg2.OperationalError: connection to server on socket "/var/run/postgresql/.s.PGSQL.5432" failed: No such file or directory`
This means the **`DATABASE_URL`** environment variable isn't set (or is
empty) on your Render service. When psycopg2 doesn't get a connection string,
it defaults to trying a local Unix socket — which doesn't exist on Render's
web service, since your database lives on Supabase, not on Render itself.
Fix:
1. Go to your Render service → **Environment**.
2. Add `DATABASE_URL` with your Supabase connection string as the value (Supabase: **Project Settings → Database → Connection string**).
3. Redeploy.

This project now raises a clear error naming exactly this (rather than the
cryptic socket message above) if `DATABASE_URL` is missing, to make this
faster to diagnose in the future.

### `ImportError: ... psycopg2/_psycopg.cpython-314-x86_64-linux-gnu.so: undefined symbol: _PyInterpreterState_Get`
This means Render built the app using a newer Python version than
`psycopg2-binary` had prebuilt wheels for, so pip fell back to an
incompatible build. Render **no longer reliably honors `runtime.txt`** — that
file is deprecated. This project now pins Python the way Render actually
supports:
- A `.python-version` file at the repo root (already included, set to `3.12.7`).
- For extra certainty, you can also set the **`PYTHON_VERSION`** environment variable to `3.12.7` in the Render dashboard — it takes precedence over `.python-version` and is the most authoritative way to pin the version.
- `requirements.txt` also now pins `psycopg2-binary==2.9.12`, which has official prebuilt wheels for newer Python versions (3.12/3.13/3.14) as extra insurance even if the Python version pinning is ever overridden.

If you still see a Python version mismatch after this, check your Render
service's **Settings** page — the runtime shown at the top must say "Python
3", and the environment variables list should show `PYTHON_VERSION` (if you
set it) actually taking effect in the build log's very first lines.

### `bash: line 1: gunicorn: command not found`
This means the `gunicorn` executable isn't resolvable on Render's `$PATH` at
start-time, even when correctly installed. Fixed in this project by using
**`python -m gunicorn ...`** instead of bare `gunicorn ...` — invoking it as a
Python module bypasses PATH lookup entirely. This is already the Start
Command in `Procfile` and `render.yaml`. If you still see this:
- Confirm `requirements.txt` on GitHub itself (not just locally) lists `gunicorn==22.0.0`.
- Use **Manual Deploy → Clear build cache & deploy**.
- Check the build log for a line like `Installing collected packages: ... gunicorn`.

### `No open ports detected`
Gunicorn was running but not listening on the port Render expects. Fixed by
`--bind 0.0.0.0:$PORT` in the Start Command (already applied here).

### `psycopg2.errors.UniqueViolation: duplicate key value violates unique constraint "users_username_key"`
This happens if `init_db.py` is run without the `--if-missing` flag against a
database that's already seeded — it will try to re-insert the same demo
accounts and crash. Always use `python init_db.py --if-missing` in any
automated build/deploy step. This project's `init_db.py` now checks for
existing data before seeding, so re-running it (e.g., on every Render
redeploy) is safe and simply skips re-seeding instead of crashing.

### Admin/user pages look unstyled or oddly stacked
This app loads Tailwind CSS from a CDN, plus the Manrope/Inter fonts from
Google Fonts. If `cdn.tailwindcss.com` or `fonts.googleapis.com` are blocked
on your network (or in a restricted testing/sandbox environment), the
affected piece will fall back to unstyled HTML. This isn't an app bug — check
that outbound requests to those domains aren't being blocked by a firewall,
proxy, or network policy. A normal browser on a normal internet connection
(including Render's
production environment) has no issue reaching any of them.

---

## 7. Notes for production hardening

- `BHUMI_SECRET_KEY` must be a long, random, secret value in production — never reuse the development fallback in `app.py`.
- Rotate all demo account passwords listed above before letting anyone but you access the deployed instance.
- Ensure the app is only ever served over HTTPS in production (Render provides this automatically on `onrender.com` domains and custom domains with a certificate).
- Password resets are admin-mediated by design (the "Forgot password?" popup on login points users to their admin) — there's no self-service reset flow to secure or maintain.
- Generate your own VAPID key pair for push notifications rather than using the shipped default (see "Generating your own VAPID keys" above) — the default is public since it's committed in this repo's source.
