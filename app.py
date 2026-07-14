import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from supabase import create_client, Client
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'default-dev-key')

# Supabase Configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- DECORATORS FOR ACCESS CONTROL ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'admin':
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# --- AUTHENTICATION ROUTES ---
@app.route('/')
def index():
    if 'user_id' in session:
        if session.get('role') == 'admin':
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('intern_dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        # Authenticate against Supabase users table
        response = supabase.table('users').select('*').eq('email', email).eq('password', password).execute()
        users = response.data
        
        if users:
            user = users[0]
            session['user_id'] = user['id']
            session['role'] = user['role']
            session['name'] = user['name']
            
            if user['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('intern_dashboard'))
        else:
            flash("Invalid credentials. Please try again.")
            
    return render_template('login.html')

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        flash("Password reset link sent to your email.")
        return redirect(url_for('login'))
    return render_template('forgot_password.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- INTERN / CAMPUS AMBASSADOR DASHBOARD ---
@app.route('/dashboard')
@login_required
def intern_dashboard():
    # Fetch tasks and resources
    tasks_response = supabase.table('tasks').select('*').execute()
    resources_response = supabase.table('resources').select('*').execute()
    
    # Fetch user's completed tasks
    completions = supabase.table('task_completions').select('*').eq('user_id', session['user_id']).execute()
    
    return render_template('intern_dashboard.html', 
                           tasks=tasks_response.data, 
                           resources=resources_response.data,
                           completions=completions.data)

# --- ADMIN DASHBOARD & CRUD ROUTES ---
@app.route('/admin')
@admin_required
def admin_dashboard():
    # Fetch categorized users
    all_users = supabase.table('users').select('*').execute().data
    admins = [u for u in all_users if u['role'] == 'admin']
    interns = [u for u in all_users if u['role'] == 'intern']
    ambassadors = [u for u in all_users if u['role'] == 'campus_ambassador']
    
    # Fetch leaderboard (all non-admins sorted by points)
    leaderboard = sorted([u for u in all_users if u['role'] != 'admin'], 
                         key=lambda x: x.get('points', 0), reverse=True)
    
    # Fetch tasks (Missions) and Resources
    tasks = supabase.table('tasks').select('*').execute().data
    resources = supabase.table('resources').select('*').execute().data
    
    return render_template('admin_dashboard.html', 
                           users=admins,
                           interns=interns, 
                           ambassadors=ambassadors,
                           leaderboard=leaderboard,
                           missions=tasks,
                           resources=resources)

# User Management (Add/Edit/Delete mapped dynamically)
@app.route('/admin/users/delete/<int:user_id>')
@admin_required
def delete_user(user_id):
    supabase.table('users').delete().eq('id', user_id).execute()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/missions/delete/<int:task_id>')
@admin_required
def delete_mission(task_id):
    supabase.table('tasks').delete().eq('id', task_id).execute()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/resources/delete/<int:resource_id>')
@admin_required
def delete_resource(resource_id):
    supabase.table('resources').delete().eq('id', resource_id).execute()
    return redirect(url_for('admin_dashboard'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)