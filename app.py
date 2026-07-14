import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from supabase import create_client, Client
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'default-super-secret-key-2026')

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
        username = request.form.get('username')
        password = request.form.get('password')
        
        # Authenticate using EXACT column names from your database
        response = supabase.table('users').select('*').eq('username', username).eq('password_hash', password).execute()
        users = response.data
        
        if users:
            user = users[0]
            session['user_id'] = user['id']
            session['role'] = user['role']
            session['name'] = user['full_name']
            
            if user['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('intern_dashboard'))
        else:
            flash("Invalid username or password. Please try again.", "error")
            
    return render_template('login.html')

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        flash("Password reset instructions have been sent to your email.", "success")
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
    tasks_response = supabase.table('tasks').select('*').execute()
    resources_response = supabase.table('resources').select('*').execute()
    return render_template('intern_dashboard.html', tasks=tasks_response.data, resources=resources_response.data)

# --- ADMIN DASHBOARD ---
@app.route('/admin')
@admin_required
def admin_dashboard():
    all_users = supabase.table('users').select('*').execute().data
    
    admins = [u for u in all_users if u.get('role') == 'admin']
    interns = [u for u in all_users if u.get('role') == 'intern']
    ambassadors = [u for u in all_users if u.get('role') == 'ambassador']
    
    leaderboard = sorted([u for u in all_users if u.get('role') != 'admin'], 
                         key=lambda x: x.get('points', 0), reverse=True)
    
    tasks = supabase.table('tasks').select('*').execute().data
    resources = supabase.table('resources').select('*').execute().data
    
    return render_template('admin_dashboard.html', 
                           admins=admins, interns=interns, ambassadors=ambassadors,
                           leaderboard=leaderboard, missions=tasks, resources=resources)

# --- ADMIN USER MANAGEMENT (CRUD) ---
@app.route('/admin/users/add', methods=['GET', 'POST'])
@admin_required
def add_user():
    if request.method == 'POST':
        try:
            supabase.table('users').insert({
                'full_name': request.form.get('full_name'),
                'username': request.form.get('username'),
                'email': request.form.get('email'),
                'password_hash': request.form.get('password'),
                'role': request.form.get('role')
            }).execute()
            flash("User created successfully!", "success")
            return redirect(url_for('admin_dashboard'))
        except Exception as e:
            flash(f"Error creating user: {str(e)}", "error")
    return render_template('add_user.html')

@app.route('/admin/users/edit/<int:user_id>', methods=['GET', 'POST'])
@admin_required
def edit_user(user_id):
    if request.method == 'POST':
        try:
            update_data = {
                'full_name': request.form.get('full_name'),
                'username': request.form.get('username'),
                'email': request.form.get('email'),
                'role': request.form.get('role')
            }
            
            # Admin Password Reset Logic
            new_password = request.form.get('new_password')
            if new_password and new_password.strip() != "":
                update_data['password_hash'] = new_password
                
            supabase.table('users').update(update_data).eq('id', user_id).execute()
            flash("User updated successfully!", "success")
            return redirect(url_for('admin_dashboard'))
        except Exception as e:
            flash("Error updating user. Please try again.", "error")

    user_response = supabase.table('users').select('*').eq('id', user_id).execute()
    if not user_response.data:
        flash("User not found.", "error")
        return redirect(url_for('admin_dashboard'))
        
    return render_template('edit_user.html', user=user_response.data[0])

@app.route('/admin/users/delete/<int:user_id>')
@admin_required
def delete_user(user_id):
    try:
        # 1. Delete connected records first (prevents Foreign Key crash)
        supabase.table('task_completions').delete().eq('user_id', user_id).execute()
        
        # 2. Now delete the actual user
        supabase.table('users').delete().eq('id', user_id).execute()
        
        flash("User deleted successfully!", "success")
    except Exception as e:
        flash("Error deleting user. Check database permissions.", "error")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/missions/delete/<int:task_id>')
@admin_required
def delete_mission(task_id):
    supabase.table('tasks').delete().eq('id', task_id).execute()
    flash("Mission deleted.", "success")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/resources/delete/<int:resource_id>')
@admin_required
def delete_resource(resource_id):
    supabase.table('resources').delete().eq('id', resource_id).execute()
    flash("Resource deleted.", "success")
    return redirect(url_for('admin_dashboard'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)