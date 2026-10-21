import os
import io
import json
from functools import wraps
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, send_file, session
from werkzeug.security import check_password_hash, generate_password_hash

from database import (
    get_db_connection, init_db,
    get_user_by_username, get_user_by_id,
    get_all_labs, get_lab_by_id,
    update_lab, create_new_lab,
    reset_user_password, get_labs_with_stats
)
from excel_handler import (
    generate_components_excel_template,
    generate_students_excel_template,
    parse_components_file,
    parse_students_file
)
from whatsapp_service import (
    generate_issue_whatsapp_message,
    generate_batch_issue_whatsapp_message,
    generate_return_whatsapp_message,
    get_whatsapp_url,
    format_phone_number
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, 'templates'),
    static_folder=os.path.join(BASE_DIR, 'static')
)
app.secret_key = 'svpcet_iiot_lab_inventory_secret_key_2026_2027'

# Ensure DB is initialized
init_db()


# ==============================================================================
# Authentication & Access Control Helpers
# ==============================================================================

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access the laboratory portal.', 'warning')
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def hod_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in as Head of Department (HOD) to access this page.', 'warning')
            return redirect(url_for('login', next=request.url))
        if session.get('role') != 'HOD_ADMIN':
            flash('Access restricted to Head of Department (HOD) only.', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def get_current_lab_id():
    """Returns active lab id (integer) for data operations. Defaults to 1."""
    active = session.get('active_lab_id')
    if active and active != 'all' and active != 0:
        try:
            return int(active)
        except (ValueError, TypeError):
            pass
    user_lab = session.get('lab_id')
    if user_lab:
        try:
            return int(user_lab)
        except (ValueError, TypeError):
            pass
    return 1


@app.context_processor
def inject_globals():
    """Inject current user, active laboratory, and all active labs into all Jinja templates."""
    active_lab = None
    all_labs = get_all_labs(active_only=True)
    active_id = session.get('active_lab_id')

    if active_id == 'all' or active_id == 0:
        active_lab = {
            'id': 0,
            'lab_name': 'All Department Laboratories',
            'lab_code': 'ALL_LABS',
            'room_no': 'IIoT Department',
            'incharge_name': 'HOD & Laboratory Staff'
        }
    elif active_id:
        active_lab = get_lab_by_id(int(active_id))
    elif 'lab_id' in session and session['lab_id']:
        active_lab = get_lab_by_id(session['lab_id'])
    else:
        active_lab = get_lab_by_id(1)

    return {
        'current_user': {
            'id': session.get('user_id'),
            'username': session.get('username'),
            'display_name': session.get('display_name'),
            'role': session.get('role'),
            'lab_id': session.get('lab_id')
        } if 'user_id' in session else None,
        'active_lab': active_lab,
        'all_labs': all_labs,
        'is_hod': session.get('role') == 'HOD_ADMIN'
    }


# ==============================================================================
# AUTHENTICATION & SESSION ROUTES
# ==============================================================================

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip().lower()
        password = request.form.get('password', '')

        user = get_user_by_username(username)
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['display_name'] = user['display_name']
            session['role'] = user['role']
            session['lab_id'] = user['lab_id']
            # Default active lab: if assigned to specific lab, use it; if HOD, default to Lab 1
            session['active_lab_id'] = user['lab_id'] if user['lab_id'] else 1

            flash(f"Welcome, {user['display_name']}! Successfully logged in.", "success")
            next_url = request.args.get('next')
            if next_url and next_url.startswith('/'):
                return redirect(next_url)
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password. Please check your credentials.', 'danger')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been safely logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/switch-lab/<lab_id>')
@login_required
def switch_lab(lab_id):
    """Switch the current active laboratory view context (HOD can switch to any or 'all')."""
    if session.get('role') != 'HOD_ADMIN':
        user_lab = session.get('lab_id')
        if str(lab_id) != str(user_lab):
            flash('Laboratory users cannot switch between different laboratories.', 'danger')
            return redirect(url_for('dashboard'))

    if lab_id == 'all' or lab_id == '0':
        session['active_lab_id'] = 0
        flash('Switched to All Department Laboratories (Master View).', 'info')
    else:
        try:
            target_id = int(lab_id)
            target_lab = get_lab_by_id(target_id)
            if target_lab:
                session['active_lab_id'] = target_id
                flash(f"Switched view to {target_lab['lab_name']}.", 'info')
            else:
                flash('Selected laboratory not found.', 'warning')
        except ValueError:
            pass

    ref = request.referrer
    if ref and ('/login' not in ref):
        return redirect(ref)
    return redirect(url_for('dashboard'))

@app.route('/change-password', methods=['POST'])
@login_required
def change_password():
    current_pass = request.form.get('current_password', '')
    new_pass = request.form.get('new_password', '')

    user = get_user_by_id(session['user_id'])
    if not user or not check_password_hash(user['password_hash'], current_pass):
        flash('Incorrect current password. Password was not changed.', 'danger')
        return redirect(request.referrer or url_for('dashboard'))

    if len(new_pass) < 4:
        flash('New password must be at least 4 characters long.', 'warning')
        return redirect(request.referrer or url_for('dashboard'))

    reset_user_password(user['id'], new_pass)
    flash('Your password has been updated successfully!', 'success')
    return redirect(request.referrer or url_for('dashboard'))


# ==============================================================================
# HOD LABORATORY MANAGEMENT ROUTES (RENAME, ADD, RESET PASSWORD)
# ==============================================================================

@app.route('/manage-labs')
@hod_required
def manage_labs():
    labs = get_labs_with_stats()
    return render_template('manage_labs.html', labs=labs)

@app.route('/manage-labs/rename', methods=['POST'])
@hod_required
def rename_lab():
    lab_id = int(request.form.get('lab_id'))
    lab_name = request.form.get('lab_name', '').strip()
    room_no = request.form.get('room_no', '').strip()
    incharge_name = request.form.get('incharge_name', '').strip()
    description = request.form.get('description', '').strip()

    if not lab_name:
        flash('Laboratory name cannot be empty.', 'danger')
        return redirect(url_for('manage_labs'))

    update_lab(lab_id, lab_name, room_no, incharge_name, description)
    flash(f'Laboratory "{lab_name}" has been renamed and updated successfully!', 'success')
    return redirect(url_for('manage_labs'))

@app.route('/manage-labs/add', methods=['POST'])
@hod_required
def add_new_lab_route():
    lab_name = request.form.get('lab_name', '').strip()
    lab_code = request.form.get('lab_code', '').strip().upper()
    room_no = request.form.get('room_no', '').strip()
    incharge_name = request.form.get('incharge_name', '').strip()
    description = request.form.get('description', '').strip()
    username = request.form.get('username', '').strip().lower()
    password = request.form.get('password', '').strip()

    if not lab_name or not lab_code or not username or not password:
        flash('Please fill in all required fields (Lab Name, Lab Code, Username, and Password).', 'danger')
        return redirect(url_for('manage_labs'))

    conn = get_db_connection()
    existing_code = conn.execute('SELECT id FROM labs WHERE lab_code = ?', (lab_code,)).fetchone()
    existing_user = conn.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()
    conn.close()

    if existing_code:
        flash(f'Error: Lab Code "{lab_code}" is already in use.', 'danger')
        return redirect(url_for('manage_labs'))

    if existing_user:
        flash(f'Error: Username "{username}" is already taken.', 'danger')
        return redirect(url_for('manage_labs'))

    create_new_lab(lab_code, lab_name, room_no, incharge_name, description, username, password)
    flash(f'New laboratory "{lab_name}" and login account "{username}" created successfully!', 'success')
    return redirect(url_for('manage_labs'))

@app.route('/manage-labs/reset-password', methods=['POST'])
@hod_required
def reset_lab_password():
    user_id = int(request.form.get('user_id'))
    new_password = request.form.get('new_password', '').strip()

    if len(new_password) < 4:
        flash('New password must be at least 4 characters long.', 'warning')
        return redirect(url_for('manage_labs'))

    reset_user_password(user_id, new_password)
    flash('User password reset successfully!', 'success')
    return redirect(url_for('manage_labs'))


# ==============================================================================
# DASHBOARD
# ==============================================================================

@app.route('/')
@login_required
def dashboard():
    conn = get_db_connection()
    active_lab_id = session.get('active_lab_id', 1)
    is_master = (active_lab_id == 'all' or active_lab_id == 0)

    # Department-wide registered students
    total_students = conn.execute('SELECT COUNT(*) FROM students').fetchone()[0]

    if is_master:
        # Aggregated stats across all labs
        total_components = conn.execute('SELECT COUNT(*) FROM components').fetchone()[0]
        active_issues = conn.execute("SELECT COUNT(*) FROM transactions WHERE status = 'ISSUED'").fetchone()[0]
        low_stock_items = conn.execute('SELECT * FROM components WHERE quantity <= min_alert_qty ORDER BY quantity ASC').fetchall()
        total_damaged = conn.execute('SELECT COALESCE(SUM(damaged_quantity), 0) FROM components').fetchone()[0]
        total_missing = conn.execute('SELECT COALESCE(SUM(missing_quantity), 0) FROM components').fetchone()[0]
        recent_transactions = conn.execute('''
            SELECT t.*, c.name as component_name, c.unit, s.name as student_name, s.roll_no, s.phone as student_phone, l.lab_name
            FROM transactions t
            JOIN components c ON t.component_id = c.id
            LEFT JOIN students s ON t.student_id = s.id
            LEFT JOIN labs l ON t.lab_id = l.id
            ORDER BY t.transaction_date DESC
            LIMIT 6
        ''').fetchall()
    else:
        lab_id = int(active_lab_id)
        total_components = conn.execute('SELECT COUNT(*) FROM components WHERE lab_id = ?', (lab_id,)).fetchone()[0]
        active_issues = conn.execute("SELECT COUNT(*) FROM transactions WHERE lab_id = ? AND status = 'ISSUED'", (lab_id,)).fetchone()[0]
        low_stock_items = conn.execute('SELECT * FROM components WHERE lab_id = ? AND quantity <= min_alert_qty ORDER BY quantity ASC', (lab_id,)).fetchall()
        total_damaged = conn.execute('SELECT COALESCE(SUM(damaged_quantity), 0) FROM components WHERE lab_id = ?', (lab_id,)).fetchone()[0]
        total_missing = conn.execute('SELECT COALESCE(SUM(missing_quantity), 0) FROM components WHERE lab_id = ?', (lab_id,)).fetchone()[0]
        recent_transactions = conn.execute('''
            SELECT t.*, c.name as component_name, c.unit, s.name as student_name, s.roll_no, s.phone as student_phone, l.lab_name
            FROM transactions t
            JOIN components c ON t.component_id = c.id
            LEFT JOIN students s ON t.student_id = s.id
            LEFT JOIN labs l ON t.lab_id = l.id
            WHERE t.lab_id = ?
            ORDER BY t.transaction_date DESC
            LIMIT 6
        ''', (lab_id,)).fetchall()

    conn.close()
    return render_template(
        'index.html',
        total_components=total_components,
        total_students=total_students,
        active_issues=active_issues,
        low_stock_count=len(low_stock_items),
        low_stock_items=low_stock_items,
        total_damaged=total_damaged,
        total_missing=total_missing,
        recent_transactions=recent_transactions,
        is_master=is_master
    )


# ==============================================================================
# COMPONENTS MANAGEMENT
# ==============================================================================

@app.route('/components')
@login_required
def list_components():
    search = request.args.get('search', '').strip()
    category = request.args.get('category', '').strip()
    
    conn = get_db_connection()
    active_lab_id = session.get('active_lab_id', 1)
    is_master = (active_lab_id == 'all' or active_lab_id == 0)

    query = '''
        SELECT c.*, l.lab_name 
        FROM components c 
        LEFT JOIN labs l ON c.lab_id = l.id 
        WHERE 1=1
    '''
    params = []

    if not is_master:
        query += ' AND c.lab_id = ?'
        params.append(get_current_lab_id())

    if search:
        query += ' AND (c.name LIKE ? OR c.specs LIKE ? OR c.rack_location LIKE ? OR c.invoice_no LIKE ? OR c.vendor_name LIKE ?)'
        params.extend([f'%{search}%', f'%{search}%', f'%{search}%', f'%{search}%', f'%{search}%'])
        
    if category:
        query += ' AND c.category = ?'
        params.append(category)
        
    query += ' ORDER BY c.name ASC'
    components = conn.execute(query, params).fetchall()
    
    # Distinct categories for filter dropdown
    if not is_master:
        categories = conn.execute('SELECT DISTINCT category FROM components WHERE lab_id = ?', (get_current_lab_id(),)).fetchall()
    else:
        categories = conn.execute('SELECT DISTINCT category FROM components').fetchall()

    conn.close()
    
    return render_template(
        'components.html',
        components=components,
        categories=categories,
        search=search,
        selected_category=category,
        is_master=is_master
    )

@app.route('/components/add', methods=['POST'])
@login_required
def add_component():
    name = request.form['name'].strip()
    category = request.form['category'].strip()
    quantity = int(request.form.get('quantity', 0))
    unit = request.form.get('unit', 'Nos').strip()
    min_alert_qty = int(request.form.get('min_alert_qty', 5))
    rack_location = request.form.get('rack_location', '').strip()
    specs = request.form.get('specs', '').strip()
    invoice_no = request.form.get('invoice_no', '').strip() or 'Opening Stock'
    purchase_date = request.form.get('purchase_date', '').strip() or datetime.now().strftime('%Y-%m-%d')
    vendor_name = request.form.get('vendor_name', '').strip() or 'Lab Store'
    lab_id = get_current_lab_id()

    try:
        unit_price = float(request.form.get('unit_price', 0.0) or 0.0)
    except:
        unit_price = 0.0
        
    if not name or not category:
        flash('Component Name and Category are required.', 'danger')
        return redirect(url_for('list_components'))
        
    conn = get_db_connection()
    conn.execute('''
        INSERT INTO components (name, category, quantity, unit, min_alert_qty, rack_location, specs, invoice_no, purchase_date, vendor_name, unit_price, lab_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (name, category, quantity, unit, min_alert_qty, rack_location, specs, invoice_no, purchase_date, vendor_name, unit_price, lab_id))
    conn.commit()
    conn.close()
    
    flash(f'Component "{name}" added successfully to laboratory stock!', 'success')
    return redirect(url_for('list_components'))

@app.route('/components/restock/<int:id>', methods=['POST'])
@login_required
def restock_component(id):
    add_qty = int(request.form.get('add_quantity', 0))
    invoice_no = request.form.get('invoice_no', '').strip()
    vendor_name = request.form.get('vendor_name', '').strip()
    purchase_date = request.form.get('purchase_date', '').strip()
    
    if add_qty <= 0:
        flash('Please enter a valid quantity greater than zero.', 'warning')
        return redirect(url_for('list_components'))
        
    conn = get_db_connection()
    if invoice_no or vendor_name or purchase_date:
        conn.execute('''
            UPDATE components 
            SET quantity = quantity + ?,
                invoice_no = CASE WHEN ? != '' THEN ? ELSE invoice_no END,
                vendor_name = CASE WHEN ? != '' THEN ? ELSE vendor_name END,
                purchase_date = CASE WHEN ? != '' THEN ? ELSE purchase_date END
            WHERE id = ?
        ''', (add_qty, invoice_no, invoice_no, vendor_name, vendor_name, purchase_date, purchase_date, id))
    else:
        conn.execute('UPDATE components SET quantity = quantity + ? WHERE id = ?', (add_qty, id))
        
    conn.commit()
    conn.close()
    
    flash(f'Successfully added +{add_qty} to stock!', 'success')
    return redirect(url_for('list_components'))

@app.route('/components/edit/<int:id>', methods=['POST'])
@login_required
def edit_component(id):
    name = request.form['name'].strip()
    category = request.form['category'].strip()
    quantity = int(request.form.get('quantity', 0))
    unit = request.form.get('unit', 'Nos').strip()
    min_alert_qty = int(request.form.get('min_alert_qty', 5))
    rack_location = request.form.get('rack_location', '').strip()
    specs = request.form.get('specs', '').strip()
    invoice_no = request.form.get('invoice_no', '').strip() or 'Opening Stock'
    purchase_date = request.form.get('purchase_date', '').strip()
    vendor_name = request.form.get('vendor_name', '').strip()
    try:
        unit_price = float(request.form.get('unit_price', 0.0) or 0.0)
    except:
        unit_price = 0.0
    
    conn = get_db_connection()
    conn.execute('''
        UPDATE components
        SET name = ?, category = ?, quantity = ?, unit = ?, min_alert_qty = ?, 
            rack_location = ?, specs = ?, invoice_no = ?, purchase_date = ?, vendor_name = ?, unit_price = ?
        WHERE id = ?
    ''', (name, category, quantity, unit, min_alert_qty, rack_location, specs, invoice_no, purchase_date, vendor_name, unit_price, id))
    conn.commit()
    conn.close()
    
    flash('Component and bill details updated successfully!', 'success')
    return redirect(url_for('list_components'))

@app.route('/components/delete/<int:id>', methods=['POST'])
@login_required
def delete_component(id):
    conn = get_db_connection()
    conn.execute('DELETE FROM components WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    flash('Component deleted successfully!', 'info')
    return redirect(url_for('list_components'))

@app.route('/components/template')
def download_components_template():
    excel_stream = generate_components_excel_template()
    return send_file(
        excel_stream,
        as_attachment=True,
        download_name='components_template.xlsx',
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

@app.route('/components/upload', methods=['POST'])
@login_required
def upload_components():
    if 'file' not in request.files:
        flash('No file selected.', 'warning')
        return redirect(url_for('list_components'))
        
    file = request.files['file']
    if file.filename == '':
        flash('Please select an Excel (.xlsx) or CSV file.', 'warning')
        return redirect(url_for('list_components'))
        
    if not (file.filename.lower().endswith('.xlsx') or file.filename.lower().endswith('.csv')):
        flash('Unsupported format. Please upload an Excel (.xlsx) or CSV file.', 'danger')
        return redirect(url_for('list_components'))
        
    records = parse_components_file(file)
    if not records:
        flash('No valid component records found in the uploaded file.', 'warning')
        return redirect(url_for('list_components'))
        
    conn = get_db_connection()
    added_count = 0
    updated_count = 0
    lab_id = get_current_lab_id()
    
    for r in records:
        existing = conn.execute('SELECT id, quantity FROM components WHERE LOWER(name) = LOWER(?) AND lab_id = ?', (r['name'], lab_id)).fetchone()
        if existing:
            conn.execute('''
                UPDATE components
                SET quantity = quantity + ?, category = ?, unit = ?, min_alert_qty = ?, 
                    rack_location = ?, specs = ?, invoice_no = ?, purchase_date = ?, vendor_name = ?, unit_price = ?
                WHERE id = ?
            ''', (r['quantity'], r['category'], r['unit'], r['min_alert_qty'], 
                  r['rack_location'], r['specs'], r['invoice_no'], r['purchase_date'], r['vendor_name'], r['unit_price'], existing['id']))
            updated_count += 1
        else:
            conn.execute('''
                INSERT INTO components (name, category, quantity, unit, min_alert_qty, rack_location, specs, invoice_no, purchase_date, vendor_name, unit_price, lab_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (r['name'], r['category'], r['quantity'], r['unit'], r['min_alert_qty'], 
                  r['rack_location'], r['specs'], r['invoice_no'], r['purchase_date'], r['vendor_name'], r['unit_price'], lab_id))
            added_count += 1
            
    conn.commit()
    conn.close()
    
    flash(f'Excel Import Complete: {added_count} new components added, {updated_count} existing components updated.', 'success')
    return redirect(url_for('list_components'))


# ==============================================================================
# STUDENTS MANAGEMENT
# ==============================================================================

@app.route('/students')
@login_required
def list_students():
    search = request.args.get('search', '').strip()
    semester = request.args.get('semester', '').strip()
    conn = get_db_connection()
    
    query = 'SELECT * FROM students WHERE 1=1'
    params = []
    
    if search:
        query += ' AND (roll_no LIKE ? OR name LIKE ? OR department LIKE ?)'
        params.extend([f'%{search}%', f'%{search}%', f'%{search}%'])
        
    if semester:
        query += ' AND (year LIKE ? OR division LIKE ?)'
        params.extend([f'%{semester}%', f'%{semester}%'])
        
    query += ' ORDER BY roll_no ASC'
    students = conn.execute(query, params).fetchall()
        
    conn.close()
    return render_template('students.html', students=students, search=search, selected_semester=semester)

@app.route('/students/add', methods=['POST'])
@login_required
def add_student():
    uid_no = (request.form.get('uid_no') or request.form.get('roll_no') or '').strip().upper()
    name = request.form['name'].strip()
    department = request.form.get('department', '').strip()
    year = request.form.get('year', 'TE').strip()
    division = request.form.get('division', '').strip().upper()
    phone = request.form.get('phone', '').strip()
    
    if not uid_no or not name:
        flash('Student UID No and Full Name are required.', 'danger')
        return redirect(url_for('list_students'))
        
    conn = get_db_connection()
    try:
        conn.execute('''
            INSERT INTO students (roll_no, name, department, year, division, phone)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (uid_no, name, department, year, division, phone))
        conn.commit()
        flash(f'Student "{name}" (UID: {uid_no}) registered successfully!', 'success')
    except Exception:
        flash(f'Error: Student UID "{uid_no}" is already registered.', 'danger')
    finally:
        conn.close()
        
    return redirect(url_for('list_students'))

@app.route('/students/edit/<int:id>', methods=['POST'])
@login_required
def edit_student(id):
    uid_no = (request.form.get('uid_no') or request.form.get('roll_no') or '').strip().upper()
    name = request.form['name'].strip()
    department = request.form.get('department', '').strip()
    year = request.form.get('year', 'TE').strip()
    division = request.form.get('division', '').strip().upper()
    phone = request.form.get('phone', '').strip()
    
    conn = get_db_connection()
    try:
        conn.execute('''
            UPDATE students
            SET roll_no = ?, name = ?, department = ?, year = ?, division = ?, phone = ?
            WHERE id = ?
        ''', (uid_no, name, department, year, division, phone, id))
        conn.commit()
        flash('Student details updated successfully!', 'success')
    except Exception:
        flash('Error: This Student UID is already assigned to another student.', 'danger')
    finally:
        conn.close()
    return redirect(url_for('list_students'))
        
@app.route('/students/delete/<int:id>', methods=['POST'])
@login_required
def delete_student(id):
    conn = get_db_connection()
    conn.execute('DELETE FROM students WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    flash('Student record deleted successfully!', 'info')
    return redirect(url_for('list_students'))

@app.route('/students/template')
def download_students_template():
    excel_stream = generate_students_excel_template()
    return send_file(
        excel_stream,
        as_attachment=True,
        download_name='students_template.xlsx',
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

@app.route('/students/upload', methods=['POST'])
@login_required
def upload_students():
    if 'file' not in request.files:
        flash('No file selected.', 'warning')
        return redirect(url_for('list_students'))
        
    file = request.files['file']
    if file.filename == '':
        flash('Please select an Excel (.xlsx) or CSV file.', 'warning')
        return redirect(url_for('list_students'))
        
    if not (file.filename.lower().endswith('.xlsx') or file.filename.lower().endswith('.csv')):
        flash('Unsupported format. Please upload an Excel (.xlsx) or CSV file.', 'danger')
        return redirect(url_for('list_students'))
        
    records = parse_students_file(file)
    if not records:
        flash('No valid student records found in the uploaded file.', 'warning')
        return redirect(url_for('list_students'))
        
    conn = get_db_connection()
    added_count = 0
    updated_count = 0
    
    for r in records:
        acad_yr = r.get('academic_year') or '2026-2027'
        existing = conn.execute('SELECT id FROM students WHERE roll_no = ?', (r['roll_no'],)).fetchone()
        if existing:
            conn.execute('''
                UPDATE students
                SET name = ?, department = ?, year = ?, division = ?, phone = ?, academic_year = ?
                WHERE id = ?
            ''', (r['name'], r['department'], r['year'], r['division'], r['phone'], acad_yr, existing['id']))
            updated_count += 1
        else:
            conn.execute('''
                INSERT INTO students (roll_no, name, department, year, division, phone, academic_year)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (r['roll_no'], r['name'], r['department'], r['year'], r['division'], r['phone'], acad_yr))
            added_count += 1
            
    conn.commit()
    conn.close()
    
    flash(f'Excel Import Complete: {added_count} new students added, {updated_count} existing students updated.', 'success')
    return redirect(url_for('list_students'))

@app.route('/download/prepared-students')
def download_prepared_students():
    filepath = os.path.join(os.path.dirname(__file__), 'students_upload.xlsx')
    return send_file(
        filepath,
        as_attachment=True,
        download_name='students_upload.xlsx',
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

@app.route('/download/prepared-components')
def download_prepared_components():
    filepath = os.path.join(os.path.dirname(__file__), 'components_upload.xlsx')
    return send_file(
        filepath,
        as_attachment=True,
        download_name='components_upload.xlsx',
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )


# ==============================================================================
# TRANSACTIONS MANAGEMENT (ISSUE / RETURN / MULTI-LAB FILTER)
# ==============================================================================

@app.route('/transactions')
@login_required
def list_transactions():
    status_filter = request.args.get('status', '').strip()
    recipient_filter = request.args.get('recipient_type', '').strip()
    search = request.args.get('search', '').strip()
    
    # Retrieve WhatsApp popup payload if flashed
    whatsapp_popup = session.pop('whatsapp_popup', None)
    
    conn = get_db_connection()
    active_lab_id = session.get('active_lab_id', 1)
    is_master = (active_lab_id == 'all' or active_lab_id == 0)

    query = '''
        SELECT t.*, c.name as component_name, c.unit, c.category, l.lab_name,
               COALESCE(NULLIF(t.recipient_name, ''), s.name, 'N/A') as display_name,
               COALESCE(NULLIF(t.recipient_id_code, ''), s.roll_no, '') as display_id_code,
               COALESCE(NULLIF(t.recipient_dept, ''), s.department, '') as display_dept,
               COALESCE(NULLIF(t.recipient_phone, ''), s.phone, '') as display_phone,
               COALESCE(NULLIF(t.recipient_type, ''), 'STUDENT') as display_type
        FROM transactions t
        JOIN components c ON t.component_id = c.id
        LEFT JOIN students s ON t.student_id = s.id
        LEFT JOIN labs l ON t.lab_id = l.id
        WHERE 1=1
    '''
    params = []

    if not is_master:
        query += ' AND t.lab_id = ?'
        params.append(get_current_lab_id())

    if status_filter:
        if status_filter == 'ISSUES':
            query += " AND t.status IN ('ALL_DAMAGED', 'ALL_MISSING', 'RETURNED_WITH_ISSUES')"
        else:
            query += ' AND t.status = ?'
            params.append(status_filter)
            
    if recipient_filter:
        query += " AND COALESCE(NULLIF(t.recipient_type, ''), 'STUDENT') = ?"
        params.append(recipient_filter)
        
    if search:
        query += ''' AND (
            t.recipient_name LIKE ? OR s.name LIKE ? OR 
            t.recipient_id_code LIKE ? OR s.roll_no LIKE ? OR 
            c.name LIKE ? OR t.purpose LIKE ?
        )'''
        params.extend([f'%{search}%', f'%{search}%', f'%{search}%', f'%{search}%', f'%{search}%', f'%{search}%'])
        
    query += ' ORDER BY t.transaction_date DESC'
    transactions = conn.execute(query, params).fetchall()
    
    # Components available in current lab for issuing
    if not is_master:
        components = conn.execute('SELECT * FROM components WHERE lab_id = ? AND quantity > 0 ORDER BY name ASC', (get_current_lab_id(),)).fetchall()
    else:
        components = conn.execute('SELECT * FROM components WHERE quantity > 0 ORDER BY name ASC').fetchall()

    students = conn.execute('SELECT id, roll_no, name, department, year, phone FROM students ORDER BY roll_no ASC').fetchall()
    staff_list = conn.execute('SELECT * FROM faculty_staff ORDER BY name ASC').fetchall()
    labs_list = conn.execute('SELECT * FROM other_labs ORDER BY lab_name ASC').fetchall()
    
    # Active pending issues map for real-time autocomplete alerts
    pending_query = '''
        SELECT t.id, t.recipient_type, t.student_id,
               COALESCE(NULLIF(t.recipient_name, ''), s.name, '') as name,
               COALESCE(NULLIF(t.recipient_id_code, ''), s.roll_no, '') as id_code,
               t.component_id,
               c.name as component_name,
               t.quantity, c.unit, t.transaction_date, t.purpose
        FROM transactions t
        JOIN components c ON t.component_id = c.id
        LEFT JOIN students s ON t.student_id = s.id
        WHERE t.status = 'ISSUED'
    '''
    pending_params = []
    if not is_master:
        pending_query += ' AND t.lab_id = ?'
        pending_params.append(get_current_lab_id())
    pending_query += ' ORDER BY t.transaction_date DESC'

    pending_rows = conn.execute(pending_query, pending_params).fetchall()
    
    active_issues_map = {
        'students': {},
        'staff': {},
        'labs': {},
        'components': {}
    }
    
    for row in pending_rows:
        item_data = {
            'component_name': row['component_name'],
            'quantity': row['quantity'],
            'unit': row['unit'],
            'date': row['transaction_date'].split()[0] if row['transaction_date'] else '',
            'purpose': row['purpose'] or '',
            'txn_id': row['id']
        }
        
        rcp_type = row['recipient_type']
        name_key = (row['name'] or '').strip().lower()
        id_key = (row['id_code'] or '').strip().lower()
        
        if rcp_type == 'STUDENT':
            target_bucket = active_issues_map['students']
            if row['student_id']:
                target_bucket.setdefault(f"id_{row['student_id']}", []).append(item_data)
        elif rcp_type == 'STAFF':
            target_bucket = active_issues_map['staff']
        else:
            target_bucket = active_issues_map['labs']
            
        if name_key:
            target_bucket.setdefault(f"name_{name_key}", []).append(item_data)
        if id_key:
            target_bucket.setdefault(f"code_{id_key}", []).append(item_data)
            
        cid = str(row['component_id'])
        c_item_data = {
            'recipient_name': row['name'] or 'Unknown',
            'recipient_id': row['id_code'] or '',
            'recipient_type': rcp_type,
            'quantity': row['quantity'],
            'unit': row['unit'],
            'date': item_data['date']
        }
        active_issues_map['components'].setdefault(cid, []).append(c_item_data)
        
    conn.close()
    
    return render_template(
        'transactions.html',
        transactions=transactions,
        components=components,
        students=students,
        staff_list=staff_list,
        labs_list=labs_list,
        active_issues_json=json.dumps(active_issues_map),
        selected_status=status_filter,
        selected_recipient=recipient_filter,
        search=search,
        whatsapp_popup=whatsapp_popup,
        is_master=is_master
    )


# ==============================================================================
# OFFICIAL TRANSACTION REGISTER REPORT (PRINT / PDF)
# ==============================================================================

@app.route('/transactions/report')
@login_required
def transaction_report():
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()
    status_filter = request.args.get('status', '').strip()
    recipient_filter = request.args.get('recipient_type', '').strip()
    search = request.args.get('search', '').strip()
    
    conn = get_db_connection()
    active_lab_id = session.get('active_lab_id', 1)
    is_master = (active_lab_id == 'all' or active_lab_id == 0)

    query = '''
        SELECT t.*, c.name as component_name, c.unit, c.category, l.lab_name,
               COALESCE(NULLIF(t.recipient_name, ''), s.name, 'N/A') as display_name,
               COALESCE(NULLIF(t.recipient_id_code, ''), s.roll_no, '') as display_id_code,
               COALESCE(NULLIF(t.recipient_dept, ''), s.department, '') as display_dept,
               COALESCE(NULLIF(t.recipient_phone, ''), s.phone, '') as display_phone,
               COALESCE(NULLIF(t.recipient_type, ''), 'STUDENT') as display_type
        FROM transactions t
        JOIN components c ON t.component_id = c.id
        LEFT JOIN students s ON t.student_id = s.id
        LEFT JOIN labs l ON t.lab_id = l.id
        WHERE 1=1
    '''
    params = []

    if not is_master:
        query += ' AND t.lab_id = ?'
        params.append(get_current_lab_id())
    
    if start_date:
        query += ' AND date(t.transaction_date) >= date(?)'
        params.append(start_date)
        
    if end_date:
        query += ' AND date(t.transaction_date) <= date(?)'
        params.append(end_date)
        
    if status_filter:
        if status_filter == 'ISSUES':
            query += " AND t.status IN ('ALL_DAMAGED', 'ALL_MISSING', 'RETURNED_WITH_ISSUES')"
        else:
            query += ' AND t.status = ?'
            params.append(status_filter)
            
    if recipient_filter:
        query += " AND COALESCE(NULLIF(t.recipient_type, ''), 'STUDENT') = ?"
        params.append(recipient_filter)
            
    if search:
        query += ''' AND (
            t.recipient_name LIKE ? OR s.name LIKE ? OR 
            t.recipient_id_code LIKE ? OR s.roll_no LIKE ? OR 
            c.name LIKE ?
        )'''
        params.extend([f'%{search}%', f'%{search}%', f'%{search}%', f'%{search}%', f'%{search}%'])
        
    query += ' ORDER BY t.transaction_date DESC'
    transactions = conn.execute(query, params).fetchall()
    
    total_txns = len(transactions)
    total_issued_qty = sum(t['quantity'] for t in transactions)
    total_good_returned = sum(t['returned_good_qty'] or 0 for t in transactions)
    total_damaged_qty = sum(t['returned_damaged_qty'] or 0 for t in transactions)
    total_missing_qty = sum(t['returned_missing_qty'] or 0 for t in transactions)
    total_pending_issues = sum(1 for t in transactions if t['status'] == 'ISSUED')
    
    student_txns_count = sum(1 for t in transactions if t['display_type'] == 'STUDENT')
    staff_txns_count = sum(1 for t in transactions if t['display_type'] == 'STAFF')
    lab_txns_count = sum(1 for t in transactions if t['display_type'] == 'OTHER_LAB')
    
    current_time = datetime.now().strftime("%d-%m-%Y %I:%M %p")
    conn.close()
    
    return render_template(
        'transaction_report.html',
        transactions=transactions,
        total_txns=total_txns,
        total_issued_qty=total_issued_qty,
        total_good_returned=total_good_returned,
        total_damaged_qty=total_damaged_qty,
        total_missing_qty=total_missing_qty,
        total_pending_issues=total_pending_issues,
        student_txns_count=student_txns_count,
        staff_txns_count=staff_txns_count,
        lab_txns_count=lab_txns_count,
        start_date=start_date,
        end_date=end_date,
        status_filter=status_filter,
        recipient_filter=recipient_filter,
        search=search,
        current_time=current_time,
        is_master=is_master
    )


# ==============================================================================
# ISSUE COMPONENT (OUT)
# ==============================================================================

@app.route('/transactions/issue', methods=['POST'])
@login_required
def issue_component():
    recipient_type = request.form.get('recipient_type', 'STUDENT').strip().upper()
    purpose = request.form.get('purpose', '').strip()
    lab_id = get_current_lab_id()

    conn = get_db_connection()

    # Determine Recipient Information
    student_id = None
    recipient_name = ""
    recipient_id_code = ""
    recipient_dept = ""
    final_phone = ""

    if recipient_type == 'STUDENT':
        student_id_val = request.form.get('student_id')
        if not student_id_val:
            conn.close()
            flash('Please select a student.', 'danger')
            return redirect(url_for('list_transactions'))
        try:
            student_id = int(student_id_val)
        except ValueError:
            conn.close()
            flash('Invalid student selected.', 'danger')
            return redirect(url_for('list_transactions'))

        student = conn.execute('SELECT * FROM students WHERE id = ?', (student_id,)).fetchone()
        if not student:
            conn.close()
            flash('Student record not found.', 'danger')
            return redirect(url_for('list_transactions'))

        student_phone = request.form.get('student_phone', '').strip()
        final_phone = student_phone if student_phone else (student['phone'] or '').strip()
        digits_only = ''.join(filter(str.isdigit, final_phone))
        if len(digits_only) < 10:
            conn.close()
            flash('Student mobile number is MANDATORY. Please enter a valid 10-digit number.', 'danger')
            return redirect(url_for('list_transactions'))

        if student_phone and student_phone != student['phone']:
            conn.execute('UPDATE students SET phone = ? WHERE id = ?', (student_phone, student_id))

        recipient_name = student['name']
        recipient_id_code = student['roll_no']  # UID
        recipient_dept = student['department']

    elif recipient_type == 'STAFF':
        staff_name = request.form.get('staff_name', '').strip()
        staff_dept = request.form.get('staff_dept', 'Faculty / Staff').strip()
        staff_phone = request.form.get('staff_phone', '').strip()
        staff_id_code = request.form.get('staff_id_code', 'STAFF').strip() or 'STAFF'

        digits_only = ''.join(filter(str.isdigit, staff_phone))
        if not staff_name or len(digits_only) < 10:
            conn.close()
            flash('Staff Name and valid 10-digit Mobile Number are mandatory.', 'danger')
            return redirect(url_for('list_transactions'))

        recipient_name = staff_name
        recipient_id_code = staff_id_code
        recipient_dept = staff_dept
        final_phone = staff_phone

        # Auto-upsert into faculty_staff directory
        existing_st = conn.execute('SELECT id FROM faculty_staff WHERE name = ?', (staff_name,)).fetchone()
        if not existing_st and staff_name:
            conn.execute('INSERT INTO faculty_staff (name, employee_id, department, phone) VALUES (?, ?, ?, ?)',
                         (staff_name, staff_id_code, staff_dept, final_phone))
        elif existing_st and final_phone:
            conn.execute('UPDATE faculty_staff SET phone = ?, department = ?, employee_id = ? WHERE id = ?',
                         (final_phone, staff_dept, staff_id_code, existing_st['id']))

    elif recipient_type == 'OTHER_LAB':
        lab_name = request.form.get('lab_name', '').strip()
        lab_room_no = request.form.get('lab_room_no', '').strip() or 'LAB'
        lab_incharge = request.form.get('lab_incharge', '').strip()
        lab_phone = request.form.get('lab_phone', '').strip()

        digits_only = ''.join(filter(str.isdigit, lab_phone))
        if not lab_name or len(digits_only) < 10:
            conn.close()
            flash('Target Lab Name and In-Charge 10-digit Mobile Number are mandatory.', 'danger')
            return redirect(url_for('list_transactions'))

        recipient_name = f"{lab_name} (In-charge: {lab_incharge})" if lab_incharge else lab_name
        recipient_id_code = lab_room_no
        recipient_dept = lab_name
        final_phone = lab_phone

        # Auto-upsert into other_labs directory
        existing_lb = conn.execute('SELECT id FROM other_labs WHERE lab_name = ?', (lab_name,)).fetchone()
        if not existing_lb and lab_name:
            conn.execute('INSERT INTO other_labs (lab_name, incharge_name, phone, room_no, department) VALUES (?, ?, ?, ?, ?)',
                         (lab_name, lab_incharge, final_phone, lab_room_no, lab_name))
        elif existing_lb and final_phone:
            conn.execute('UPDATE other_labs SET phone = ?, incharge_name = ?, room_no = ? WHERE id = ?',
                         (final_phone, lab_incharge, lab_room_no, existing_lb['id']))

    # Extract component lists (supports both multi-row component_ids[] and legacy component_id)
    raw_comp_ids = request.form.getlist('component_ids[]') or request.form.getlist('component_id')
    raw_quantities = request.form.getlist('quantities[]') or request.form.getlist('quantity')
    raw_consumables = request.form.getlist('is_consumables[]') or request.form.getlist('is_consumable')

    items_to_process = []
    for i in range(len(raw_comp_ids)):
        cid_str = (raw_comp_ids[i] or '').strip()
        if not cid_str:
            continue
        try:
            cid = int(cid_str)
        except ValueError:
            continue

        qty_str = (raw_quantities[i] if i < len(raw_quantities) else '1') or '1'
        try:
            qty = int(qty_str)
        except ValueError:
            qty = 1

        if qty <= 0:
            continue

        is_cons = (raw_consumables[i] if i < len(raw_consumables) else 'no').strip().lower()
        items_to_process.append({
            'component_id': cid,
            'quantity': qty,
            'is_consumable': is_cons
        })

    if not items_to_process:
        conn.close()
        flash('Please select at least one valid component and quantity to issue.', 'danger')
        return redirect(url_for('list_transactions'))

    # Aggregate quantities requested per component to validate total stock
    comp_totals = {}
    for it in items_to_process:
        cid = it['component_id']
        comp_totals[cid] = comp_totals.get(cid, 0) + it['quantity']

    # Stock Validation Pass (Atomicity: fail early if any item is short)
    comp_lookup = {}
    for cid, total_qty in comp_totals.items():
        comp = conn.execute('SELECT * FROM components WHERE id = ?', (cid,)).fetchone()
        if not comp:
            conn.close()
            flash(f'Component record not found (ID: {cid}).', 'danger')
            return redirect(url_for('list_transactions'))
        if comp['quantity'] < total_qty:
            conn.close()
            flash(f"Insufficient stock for '{comp['name']}'! Requested: {total_qty} {comp['unit']}, Available: {comp['quantity']} {comp['unit']}.", 'danger')
            return redirect(url_for('list_transactions'))
        comp_lookup[cid] = comp

    # Deduct stock and record transactions
    issued_items_summary = []
    for it in items_to_process:
        cid = it['component_id']
        comp = comp_lookup[cid]
        qty = it['quantity']
        status = 'CONSUMED' if it['is_consumable'] == 'yes' or comp['category'] == 'Consumable' else 'ISSUED'

        # 1. Deduct stock
        conn.execute('UPDATE components SET quantity = quantity - ? WHERE id = ?', (qty, cid))

        # 2. Insert transaction
        conn.execute('''
            INSERT INTO transactions (
                component_id, student_id, recipient_type, recipient_name,
                recipient_id_code, recipient_dept, recipient_phone,
                type, quantity, purpose, status, lab_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 'OUT', ?, ?, ?, ?)
        ''', (cid, student_id, recipient_type, recipient_name,
              recipient_id_code, recipient_dept, final_phone,
              qty, purpose, status, lab_id))

        issued_items_summary.append({
            'name': comp['name'],
            'quantity': qty,
            'unit': comp['unit']
        })

    conn.commit()

    # Determine Active Lab Name for the WhatsApp receipt header
    current_lab = get_lab_by_id(lab_id)
    lab_display_name = current_lab['lab_name'] if current_lab else "Embedded Systems Lab"

    # WhatsApp Issue Notification & Popup
    wa_msg = generate_batch_issue_whatsapp_message(
        recipient_name=recipient_name,
        recipient_id=recipient_id_code,
        items_list=issued_items_summary,
        purpose=purpose,
        recipient_type=recipient_type,
        dept=recipient_dept,
        lab_name=lab_display_name
    )
    wa_url = get_whatsapp_url(final_phone, wa_msg)

    items_display_str = ", ".join(f"{x['name']} ({x['quantity']} {x['unit']})" for x in issued_items_summary)
    session['whatsapp_popup'] = {
        'title': f'{len(issued_items_summary)} Component(s) Issued Successfully!',
        'type': f'{recipient_type.title()} Issue Receipt',
        'student_name': recipient_name,
        'phone': final_phone,
        'component_name': items_display_str,
        'quantity': f"{len(issued_items_summary)} item(s) total",
        'url': wa_url,
        'message_text': wa_msg
    }

    conn.close()
    flash(f'Successfully issued {len(issued_items_summary)} component(s) to {recipient_name}!', 'success')
    return redirect(url_for('list_transactions'))


# ==============================================================================
# RETURN COMPONENT (IN)
# ==============================================================================

@app.route('/transactions/return/<int:id>', methods=['POST'])
@login_required
def return_component(id):
    conn = get_db_connection()
    txn = conn.execute('SELECT * FROM transactions WHERE id = ?', (id,)).fetchone()
    
    if not txn:
        conn.close()
        flash('Transaction record not found.', 'danger')
        return redirect(url_for('list_transactions'))
        
    if txn['status'] not in ('ISSUED', 'RETURNED_WITH_ISSUES'):
        conn.close()
        flash('This item has already been marked as returned or consumed.', 'warning')
        return redirect(url_for('list_transactions'))
        
    try:
        good_qty = int(request.form.get('good_qty', 0))
        damaged_qty = int(request.form.get('damaged_qty', 0))
        missing_qty = int(request.form.get('missing_qty', 0))
    except ValueError:
        conn.close()
        flash('Invalid quantity entered.', 'danger')
        return redirect(url_for('list_transactions'))
        
    damage_remarks = request.form.get('damage_remarks', '').strip()
    total_accounted = good_qty + damaged_qty + missing_qty
    
    if total_accounted != txn['quantity']:
        conn.close()
        flash(f'Total quantity accounted ({total_accounted}) must exactly match issued quantity ({txn["quantity"]}).', 'danger')
        return redirect(url_for('list_transactions'))
        
    if good_qty == txn['quantity']:
        status = 'RETURNED'
    elif damaged_qty == txn['quantity']:
        status = 'ALL_DAMAGED'
    elif missing_qty == txn['quantity']:
        status = 'ALL_MISSING'
    else:
        status = 'RETURNED_WITH_ISSUES'

    if good_qty > 0:
        conn.execute('UPDATE components SET quantity = quantity + ? WHERE id = ?', (good_qty, txn['component_id']))

    if damaged_qty > 0:
        conn.execute('UPDATE components SET damaged_quantity = damaged_quantity + ? WHERE id = ?', (damaged_qty, txn['component_id']))

    if missing_qty > 0:
        conn.execute('UPDATE components SET missing_quantity = missing_quantity + ? WHERE id = ?', (missing_qty, txn['component_id']))

    conn.execute('''
        UPDATE transactions
        SET status = ?,
            returned_good_qty = ?,
            returned_damaged_qty = ?,
            returned_missing_qty = ?,
            damage_remarks = ?,
            return_date = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (status, good_qty, damaged_qty, missing_qty, damage_remarks, id))
    
    conn.commit()
    
    comp = conn.execute('SELECT * FROM components WHERE id = ?', (txn['component_id'],)).fetchone()
    
    rcp_name = txn['recipient_name'] or ''
    rcp_id = txn['recipient_id_code'] or ''
    rcp_phone = txn['recipient_phone'] or ''
    rcp_type = txn['recipient_type'] or 'STUDENT'
    rcp_dept = txn['recipient_dept'] or ''
    
    if not rcp_name and txn['student_id']:
        student = conn.execute('SELECT * FROM students WHERE id = ?', (txn['student_id'],)).fetchone()
        if student:
            rcp_name = student['name']
            rcp_id = student['roll_no']
            rcp_phone = student['phone']
            
    if rcp_phone:
        wa_msg = generate_return_whatsapp_message(
            recipient_name=rcp_name,
            recipient_id=rcp_id,
            component_name=comp['name'],
            total_qty=txn['quantity'],
            unit=comp['unit'],
            good_qty=good_qty,
            damaged_qty=damaged_qty,
            missing_qty=missing_qty,
            remarks=damage_remarks,
            recipient_type=rcp_type,
            dept=rcp_dept
        )
        wa_url = get_whatsapp_url(rcp_phone, wa_msg)
        
        session['whatsapp_popup'] = {
            'title': 'Return Processed Successfully!',
            'type': f'{rcp_type.title()} Return Receipt',
            'student_name': rcp_name,
            'phone': rcp_phone,
            'component_name': comp['name'],
            'quantity': f"{txn['quantity']} {comp['unit']}",
            'url': wa_url,
            'message_text': wa_msg
        }
        
    conn.close()
    flash(f'Return processed successfully! ({good_qty} Good, {damaged_qty} Damaged, {missing_qty} Missing) for {rcp_name}', 'success')
    return redirect(url_for('list_transactions'))


# ==============================================================================
# MAIN ENTRYPOINT
# ==============================================================================

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
