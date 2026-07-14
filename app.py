import os
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
from functools import wraps
from supabase import create_client, Client

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "fallback-secret-key-string-12345")

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- ACCESS DECORATORS ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session: return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'admin': return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# --- ROUTES ---
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('admin_dashboard' if session.get('role') == 'admin' else 'intern_dashboard'))
    return redirect(url_for('login'))

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static', 'img'), 'bhumi_logo.png', mimetype='image/png')

@app.route('/admin')
@admin_required
def admin_dashboard():
    days = int(request.args.get('days', 30))
    limit_date = (datetime.now() - timedelta(days=days)).isoformat()
    
    users = supabase.table('users').select('*').execute().data or []
    donations = supabase.table('donations').select('*, users(full_name)').gte('created_at', limit_date).execute().data or []
    announcements = supabase.table('announcements').select('*').order('created_at', desc=True).limit(5).execute().data or []
    
    # Simple Metrics
    interns = [u for u in users if u['role'] == 'intern']
    ambassadors = [u for u in users if u['role'] == 'ambassador']
    approved = [d for d in donations if d['status'] == 'approved']
    total_raised = sum(float(d.get('amount', 0)) for d in approved)
    
    return render_template('admin_dashboard.html', interns=interns, ambassadors=ambassadors, 
                           total_raised=total_raised, announcements=announcements, selected_days=days)

@app.route('/admin/announcement', methods=['POST'])
@admin_required
def post_announcement():
    content = request.form.get('content')
    if content: supabase.table('announcements').insert({'content': content}).execute()
    return redirect(url_for('admin_dashboard'))

@app.route('/dashboard')
@login_required
def intern_dashboard():
    u_id = session['user_id']
    donations = supabase.table('donations').select('*').eq('user_id', u_id).execute().data or []
    announcements = supabase.table('announcements').select('*').order('created_at', desc=True).limit(5).execute().data or []
    approved = [d for d in donations if d['status'] == 'approved']
    
    return render_template('intern_dashboard.html', my_donations=donations, 
                           total_raised=sum(float(d.get('amount', 0)) for d in approved),
                           announcements=announcements)

# --- LOGIN/LOGOUT ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = supabase.table('users').select('*').eq('username', request.form.get('username')).execute().data
        if user and user[0]['password_hash'] == request.form.get('password'):
            session.update({'user_id': user[0]['id'], 'role': user[0]['role']})
            return redirect(url_for('admin_dashboard' if user[0]['role'] == 'admin' else 'intern_dashboard'))
        flash("Invalid login", "error")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)