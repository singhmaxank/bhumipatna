import os
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
from functools import wraps
from supabase import create_client, Client

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "fallback-secret-key-string-12345")

# Supabase Client Initialization Pipeline
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- SYSTEM ACCESS CONTROLLERS ---
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
            flash("Unauthorized access role attempt blocked.", "error")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# --- ANCHOR RUNTIME GLOBAL FAVICON HANDLER ---
@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static', 'img'), 'bhumi_logo.png', mimetype='image/png')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        try:
            res = supabase.table('users').select('*').eq('username', username).execute().data
            if res and res[0]['password_hash'] == password:
                session['user_id'] = res[0]['id']
                session['username'] = res[0]['username']
                session['name'] = res[0]['full_name']
                session['role'] = res[0]['role']
                return redirect(url_for('admin_dashboard' if res[0]['role'] == 'admin' else 'intern_dashboard'))
            flash("Invalid operational credentials submitted.", "error")
        except Exception as e:
            flash(f"System Authenticator Exception: {str(e)}", "error")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- ADMINISTRATIVE WORKSTATION CONTROLLER ---
@app.route('/admin')
@admin_required
def admin_dashboard():
    try:
        users = supabase.table('users').select('*').execute().data or []
        donations = supabase.table('donations').select('*, users(full_name)').execute().data or []
        
        interns = [u for u in users if u['role'] == 'intern']
        ambassadors = [u for u in users if u['role'] == 'ambassador']
        admins = [u for u in users if u['role'] == 'admin']
        
        approved_donations = [d for d in donations if d['status'] == 'approved']
        total_raised = sum(float(d['amount'] or 0) for d in approved_donations)
        
        # User dynamic allocation parser
        for u in users:
            u_dons = [d for d in approved_donations if d['user_id'] == u['id']]
            u['total_raised'] = sum(float(d['amount'] or 0) for d in u_dons)
            head = next((h for h in admins if h['id'] == u.get('head_id')), None)
            u['head_name'] = head['full_name'] if head else "Main System Admin"

        leaderboard = sorted([u for u in users if u['role'] in ['intern', 'ambassador']], key=lambda x: x['total_raised'], reverse=True)
        
        return render_template('admin_dashboard.html', interns=interns, ambassadors=ambassadors, total_platform_raised=total_raised, leaderboard=leaderboard)
    except Exception as e:
        flash(f"Data Core Read Error: {str(e)}", "error")
        return render_template('admin_dashboard.html', interns=[], ambassadors=[], total_platform_raised=0, leaderboard=[])

# --- ACCOUNT COMPILER CONTROL MODS ---
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
            if request.form.get('head_id'): 
                insert_data['head_id'] = int(request.form.get('head_id'))

            supabase.table('users').insert(insert_data).execute()
            flash("New application account record registered successfully.", "success")
            return redirect(url_for('admin_dashboard'))
        except Exception as e:
            flash(f"Write Exception: {str(e)}", "error")
            
    admins = supabase.table('users').select('id, full_name').eq('role', 'admin').execute().data or []
    all_users = supabase.table('users').select('id, username, full_name').execute().data or []
    all_users = sorted(all_users, key=lambda x: x['full_name'])
    return render_template('add_user.html', admins=admins, all_users=all_users)

@app.route('/admin/users/quick_reset', methods=['POST'])
@admin_required
def quick_reset():
    user_id = request.form.get('user_id')
    new_password = request.form.get('new_password')
    try:
        supabase.table('users').update({'password_hash': new_password}).eq('id', user_id).execute()
        flash("Target credential override update executed successfully.", "success")
    except Exception as e:
        flash(f"Credential Write Fault: {str(e)}", "error")
    return redirect(url_for('add_user'))

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
            if request.form.get('head_id'):
                update_data['head_id'] = int(request.form.get('head_id'))
            else:
                update_data['head_id'] = None
                
            if request.form.get('new_password'):
                update_data['password_hash'] = request.form.get('new_password')
                
            supabase.table('users').update(update_data).eq('id', user_id).execute()
            flash("User parameters modified successfully.", "success")
            return redirect(url_for('admin_dashboard'))
        except Exception as e:
            flash(f"Update Fault: {str(e)}", "error")
            
    user = supabase.table('users').select('*').eq('id', user_id).execute().data[0]
    admins = supabase.table('users').select('id, full_name').eq('role', 'admin').execute().data or []
    return render_template('edit_user.html', user=user, admins=admins)

@app.route('/admin/users/delete/<int:user_id>')
@admin_required
def delete_user(user_id):
    try:
        supabase.table('users').delete().eq('id', user_id).execute()
        flash("Record erased from directory.", "success")
    except Exception as e:
        flash(f"Erase Error Constraints: {str(e)}", "error")
    return redirect(url_for('admin_dashboard'))

# --- VERIFICATION PROTOCOL QUEUE CONTROLLERS ---
@app.route('/admin/verify')
@admin_required
def verify_donations():
    try:
        donations = supabase.table('donations').select('*, users(full_name)').eq('status', 'pending').execute().data or []
        return render_template('admin_verify.html', donations=donations)
    except Exception as e:
        flash(f"Queue Load Error: {str(e)}", "error")
        return render_template('admin_verify.html', donations=[])

@app.route('/admin/verify/<int:don_id>/<string:status>')
@admin_required
def update_status(don_id, status):
    if status in ['approved', 'rejected']:
        try:
            supabase.table('donations').update({'status': status}).eq('id', don_id).execute()
            flash(f"Transaction data updated to state: {status.upper()}.", "success")
        except Exception as e:
            flash(f"Status Write Exception: {str(e)}", "error")
    return redirect(url_for('verify_donations'))

# --- COMPREHENSIVE COMPRESSION EXPORT (PDF ENGINE DATA) ---
@app.route('/admin/export')
@admin_required
def export_pdf():
    try:
        all_users = supabase.table('users').select('*').in_('role', ['intern', 'ambassador']).execute().data or []
        donations = supabase.table('donations').select('*').eq('status', 'approved').execute().data or []
        
        for u in all_users:
            user_donations = [d for d in donations if d.get('user_id') == u.get('id')]
            u['total_raised'] = sum(float(d.get('amount') or 0) for d in user_donations)
            
        all_users = sorted(all_users, key=lambda x: x.get('total_raised', 0), reverse=True)
        return render_template('export.html', users=all_users)
    except Exception as e:
        flash(f"Data Assembly Error: {str(e)}", "error")
        return redirect(url_for('admin_dashboard'))

# --- WORKSTATION INTERN LOG COMPILERS ---
@app.route('/dashboard')
@login_required
def intern_dashboard():
    u_id = session['user_id']
    try:
        my_donations = supabase.table('donations').select('*').eq('user_id', u_id).execute().data or []
        user_meta = supabase.table('users').select('*').eq('id', u_id).execute().data[0]
        
        approved_donations = [d for d in my_donations if d['status'] == 'approved']
        total_donated = sum(float(d['amount'] or 0) for d in approved_donations)
        
        head_name = "Main System Admin"
        if user_meta.get('head_id'):
            head_data = supabase.table('users').select('full_name').eq('id', user_meta['head_id']).execute().data
            if head_data: head_name = head_data[0]['full_name']
            
        return render_template('intern_dashboard.html', my_donations=my_donations, total_donated=total_donated, head_name=head_name, progress_percent=45, days_left=14)
    except Exception as e:
        flash(f"Dashboard Read Failure: {str(e)}", "error")
        return render_template('intern_dashboard.html', my_donations=[], total_donated=0, head_name="Error", progress_percent=0, days_left=0)

@app.route('/submit-donation', methods=['POST'])
@login_required
def submit_donation():
    try:
        insert_data = {
            'user_id': session['user_id'],
            'donor_name': request.form.get('donor_name'),
            'donor_phone': request.form.get('donor_phone'),
            'amount': float(request.form.get('amount')),
            'utr': request.form.get('utr'),
            'screenshot_url': request.form.get('screenshot_url'),
            'status': 'pending'
        }
        supabase.table('donations').insert(insert_data).execute()
        flash("Impact log record transmitted to verification framework queue.", "success")
    except Exception as e:
        flash(f"Data Transmission Interrupted: {str(e)}", "error")
    return redirect(url_for('intern_dashboard'))

if __name__ == '__main__':
    app.run(debug=True)