import os
from datetime import datetime, date
from flask import Flask, render_template, request, redirect, url_for, session, flash
from supabase import create_client, Client
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'default-super-secret-key-2026')

# Supabase Configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- DECORATORS ---
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

# --- ROUTES ---
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
        response = supabase.table('users').select('*').eq('username', username).eq('password_hash', password).execute()
        users = response.data
        if users:
            user = users[0]
            session['user_id'] = user['id']
            session['role'] = user['role']
            session['name'] = user['full_name']
            if user['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
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

@app.route('/dashboard')
@login_required
def intern_dashboard():
    try:
        user_response = supabase.table('users').select('*').eq('id', session['user_id']).execute()
        user_data = user_response.data[0] if user_response.data else {}
        
        tenure_start = user_data.get('tenure_start')
        tenure_end = user_data.get('tenure_end')
        progress_percent = 0
        days_left = 0
        
        if tenure_start and tenure_end:
            try:
                start_date = datetime.strptime(str(tenure_start).split('T')[0], '%Y-%m-%d').date()
                end_date = datetime.strptime(str(tenure_end).split('T')[0], '%Y-%m-%d').date()
                today = date.today()
                total_days = (end_date - start_date).days
                if total_days > 0:
                    days_passed = max(0, min((today - start_date).days, total_days))
                    progress_percent = int((days_passed / total_days) * 100)
                    days_left = total_days - days_passed
            except: pass 

        donations_data = supabase.table('donations').select('*').execute().data or []
        raised_by_user = {}
        for d in donations_data:
            uid = d.get('user_id')
            raised_by_user[uid] = raised_by_user.get(uid, 0) + float(d.get('amount') or 0)

        all_users = supabase.table('users').select('*').execute().data
        for u in all_users:
            u['total_raised'] = raised_by_user.get(u.get('id'), 0)
            
        leaderboard = sorted([u for u in all_users if u.get('role') != 'admin'], 
                             key=lambda x: x.get('total_raised', 0), reverse=True)[:5]
        
        total_donated = raised_by_user.get(session['user_id'], 0)
        tasks = supabase.table('tasks').select('*').execute().data or []
        resources = supabase.table('resources').select('*').execute().data or []
        
        return render_template('intern_dashboard.html', tasks=tasks, resources=resources, user_data=user_data,
                               progress_percent=progress_percent, days_left=days_left,
                               leaderboard=leaderboard, total_donated=total_donated)
    except Exception as e:
        return f"<h3>Dashboard Error:</h3><p>{str(e)}</p>"

@app.route('/submit-donation', methods=['POST'])
@login_required
def submit_donation():
    try:
        supabase.table('donations').insert({
            'user_id': session['user_id'],
            'donor_name': request.form.get('donor_name'),
            'donor_phone': request.form.get('donor_phone'),
            'amount': request.form.get('amount'),
            'utr': request.form.get('utr'),
            'screenshot_url': request.form.get('screenshot_url')
        }).execute()
        flash("Donation logged successfully! Pending admin verification.", "success")
    except Exception as e:
        flash(f"Error logging donation. Error: {str(e)}", "error")
    return redirect(url_for('intern_dashboard'))

@app.route('/admin')
@admin_required
def admin_dashboard():
    all_users = supabase.table('users').select('*').execute().data or []
    donations_data = supabase.table('donations').select('*').execute().data or []
    tasks = supabase.table('tasks').select('*').execute().data or []
    resources = supabase.table('resources').select('*').execute().data or []
    
    today = date.today()
    total_platform_raised = 0

    for u in all_users:
        start = u.get('tenure_start')
        end = u.get('tenure_end')
        u['progress'] = 0
        u['days_left'] = 0
        if start and end:
            try:
                s_date = datetime.strptime(str(start).split('T')[0], '%Y-%m-%d').date()
                e_date = datetime.strptime(str(end).split('T')[0], '%Y-%m-%d').date()
                t_days = (e_date - s_date).days
                if t_days > 0:
                    passed = max(0, min((today - s_date).days, t_days))
                    u['progress'] = int((passed / t_days) * 100)
                    u['days_left'] = t_days - passed
            except: pass

        user_donations = [d for d in donations_data if d.get('user_id') == u.get('id')]
        u['total_raised'] = sum(float(d.get('amount') or 0) for d in user_donations)
        total_platform_raised += u['total_raised']

    admins = [u for u in all_users if u.get('role') == 'admin']
    interns = [u for u in all_users if u.get('role') == 'intern']
    ambassadors = [u for u in all_users if u.get('role') == 'ambassador']
    leaderboard = sorted([u for u in all_users if u.get('role') != 'admin'], 
                         key=lambda x: x.get('total_raised', 0), reverse=True)
    
    return render_template('admin_dashboard.html', admins=admins, interns=interns, ambassadors=ambassadors,
                           leaderboard=leaderboard, missions=tasks, resources=resources, total_platform_raised=total_platform_raised)

@app.route('/admin/users/add', methods=['GET', 'POST'])
@admin_required
def add_user():
    if request.method == 'POST':
        try:
            insert_data = {
                'full_name': request.form.get('full_name'),
                'username': request.form.get('username'),
                'email': request.form.get('email'),
                'password_hash': request.form.get('password'),
                'role': request.form.get('role')
            }
            if request.form.get('tenure_start'): insert_data['tenure_start'] = request.form.get('tenure_start')
            if request.form.get('tenure_end'): insert_data['tenure_end'] = request.form.get('tenure_end')

            supabase.table('users').insert(insert_data).execute()
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
                'role': request.form.get('role'),
                'tenure_start': request.form.get('tenure_start') or None,
                'tenure_end': request.form.get('tenure_end') or None
            }
            new_password = request.form.get('new_password')
            if new_password and new_password.strip() != "":
                update_data['password_hash'] = new_password
                
            supabase.table('users').update(update_data).eq('id', user_id).execute()
            flash("User updated successfully!", "success")
            return redirect(url_for('admin_dashboard'))
        except Exception as e:
            flash(f"Error updating user: {str(e)}", "error")

    user_response = supabase.table('users').select('*').eq('id', user_id).execute()
    if not user_response.data:
        flash("User not found.", "error")
        return redirect(url_for('admin_dashboard'))
    return render_template('edit_user.html', user=user_response.data[0])

@app.route('/admin/users/delete/<int:user_id>')
@admin_required
def delete_user(user_id):
    try:
        try: supabase.table('task_completions').delete().eq('user_id', user_id).execute()
        except: pass 
        try: supabase.table('donations').delete().eq('user_id', user_id).execute()
        except: pass
        supabase.table('users').delete().eq('id', user_id).execute()
        flash("User deleted successfully!", "success")
    except Exception as e:
        flash(f"Database Blocked Deletion: {str(e)}", "error")
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