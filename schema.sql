-- Bhumi NGO Portal Database Schema

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('admin', 'intern', 'ambassador')),
    full_name TEXT NOT NULL,
    email TEXT,
    phone TEXT,
    tenure_start DATE,
    tenure_end DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Added later: lets each intern/ambassador be assigned to a managing admin.
-- No formal FK constraint (to keep this migration trivially idempotent) —
-- validity is enforced at the application layer instead.
ALTER TABLE users ADD COLUMN IF NOT EXISTS assigned_admin_id INTEGER;

CREATE TABLE IF NOT EXISTS donations (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    donor_name TEXT NOT NULL,
    amount REAL NOT NULL,
    drive_link TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'approved', 'rejected')),
    admin_note TEXT,
    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    reviewed_at TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Added after the initial release: donor phone and UTR/transaction ID.
-- Safe to re-run against an existing database — these are no-ops if the
-- columns already exist, so this patches already-deployed databases too.
ALTER TABLE donations ADD COLUMN IF NOT EXISTS donor_phone TEXT;
ALTER TABLE donations ADD COLUMN IF NOT EXISTS utr_reference TEXT;
-- Added later: optionally ties a donation to a specific campaign goal so
-- that campaign's progress bar reflects only donations intended for it.
-- No formal FK constraint, same reasoning as assigned_admin_id above.
ALTER TABLE donations ADD COLUMN IF NOT EXISTS campaign_id INTEGER;

-- Added later: optional link tagging a donation to a specific campaign goal,
-- so that campaign's progress bar fills as tagged donations get verified.
ALTER TABLE donations ADD COLUMN IF NOT EXISTS campaign_id INTEGER;

CREATE TABLE IF NOT EXISTS tasks (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    deadline DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER,
    FOREIGN KEY (created_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS task_completions (
    id SERIAL PRIMARY KEY,
    task_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(task_id, user_id),
    FOREIGN KEY (task_id) REFERENCES tasks(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS resources (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    category TEXT NOT NULL,
    link TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS announcements (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER,
    FOREIGN KEY (created_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS campaign_goals (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    target_amount REAL NOT NULL,
    start_date DATE,
    end_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER,
    FOREIGN KEY (created_by) REFERENCES users(id)
);

-- Stores one row per browser/device push subscription. A user can have
-- several (e.g. phone + laptop); each is targeted individually when sending
-- a notification, and removed automatically if the browser reports it as
-- expired/invalid.
CREATE TABLE IF NOT EXISTS push_subscriptions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    endpoint TEXT UNIQUE NOT NULL,
    p256dh TEXT NOT NULL,
    auth TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
