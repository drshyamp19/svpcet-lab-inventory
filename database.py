import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'lab_inventory.db')

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Components / Consumables Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS components (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 0,
            unit TEXT DEFAULT 'Nos',
            min_alert_qty INTEGER DEFAULT 5,
            rack_location TEXT,
            specs TEXT,
            damaged_quantity INTEGER DEFAULT 0,
            missing_quantity INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 2. Students Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            roll_no TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            department TEXT NOT NULL,
            year TEXT NOT NULL,
            division TEXT,
            phone TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 3. Transactions / Issues (IN / OUT) Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            component_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            type TEXT NOT NULL, -- 'OUT' (Issue) or 'IN' (Restock / Return)
            quantity INTEGER NOT NULL,
            purpose TEXT,
            status TEXT NOT NULL, -- 'ISSUED', 'RETURNED', 'DAMAGED', 'MISSING', 'RETURNED_WITH_ISSUES', 'CONSUMED'
            returned_good_qty INTEGER DEFAULT 0,
            returned_damaged_qty INTEGER DEFAULT 0,
            returned_missing_qty INTEGER DEFAULT 0,
            damage_remarks TEXT,
            transaction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            return_date TIMESTAMP,
            remarks TEXT,
            FOREIGN KEY (component_id) REFERENCES components (id),
            FOREIGN KEY (student_id) REFERENCES students (id)
        )
    ''')

    # 4. Faculty & Staff Directory Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS faculty_staff (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            employee_id TEXT UNIQUE,
            department TEXT NOT NULL,
            designation TEXT,
            phone TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 5. Other Labs Directory Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS other_labs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lab_name TEXT UNIQUE NOT NULL,
            incharge_name TEXT,
            phone TEXT,
            room_no TEXT,
            department TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Migration: Ensure new columns exist if table was already created
    def add_col_if_not_exists(table, col, col_type):
        cursor.execute(f"PRAGMA table_info({table})")
        columns = [row[1] for row in cursor.fetchall()]
        if col not in columns:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}")

    add_col_if_not_exists('components', 'damaged_quantity', 'INTEGER DEFAULT 0')
    add_col_if_not_exists('components', 'missing_quantity', 'INTEGER DEFAULT 0')
    add_col_if_not_exists('components', 'invoice_no', 'TEXT DEFAULT ""')
    add_col_if_not_exists('components', 'purchase_date', 'TEXT DEFAULT ""')
    add_col_if_not_exists('components', 'vendor_name', 'TEXT DEFAULT ""')
    add_col_if_not_exists('components', 'unit_price', 'REAL DEFAULT 0.0')
    add_col_if_not_exists('components', 'lab_id', 'INTEGER DEFAULT 1')
    add_col_if_not_exists('transactions', 'returned_good_qty', 'INTEGER DEFAULT 0')
    add_col_if_not_exists('transactions', 'returned_damaged_qty', 'INTEGER DEFAULT 0')
    add_col_if_not_exists('transactions', 'returned_missing_qty', 'INTEGER DEFAULT 0')
    add_col_if_not_exists('transactions', 'damage_remarks', 'TEXT')
    add_col_if_not_exists('transactions', 'recipient_type', 'TEXT DEFAULT "STUDENT"')
    add_col_if_not_exists('transactions', 'recipient_name', 'TEXT DEFAULT ""')
    add_col_if_not_exists('transactions', 'recipient_id_code', 'TEXT DEFAULT ""')
    add_col_if_not_exists('transactions', 'recipient_dept', 'TEXT DEFAULT ""')
    add_col_if_not_exists('transactions', 'recipient_phone', 'TEXT DEFAULT ""')
    add_col_if_not_exists('transactions', 'lab_id', 'INTEGER DEFAULT 1')
    add_col_if_not_exists('students', 'academic_year', 'TEXT DEFAULT "2026-2027"')

    # 6. Labs Table (Multi-Lab Management)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS labs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lab_code TEXT UNIQUE NOT NULL,
            lab_name TEXT NOT NULL,
            room_no TEXT,
            incharge_name TEXT,
            description TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 7. Users Table (Authentication & Access Control)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            display_name TEXT NOT NULL,
            role TEXT NOT NULL, -- 'HOD_ADMIN' or 'LAB_USER'
            lab_id INTEGER,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (lab_id) REFERENCES labs (id)
        )
    ''')

    # Ensure existing records belong to Lab 1 (Embedded Systems Lab)
    cursor.execute("UPDATE components SET lab_id = 1 WHERE lab_id IS NULL OR lab_id = 0")
    cursor.execute("UPDATE transactions SET lab_id = 1 WHERE lab_id IS NULL OR lab_id = 0")

    # Insert default labs if table is empty
    cursor.execute('SELECT COUNT(*) FROM labs')
    if cursor.fetchone()[0] == 0:
        default_labs = [
            (1, 'LAB_EMBEDDED', 'Embedded Systems Laboratory', 'Room B-204, IIoT Wing', 'Prof. In-Charge (Embedded)', 'Microcontrollers (ESP32/Arduino), IoT sensors, actuators, and embedded development boards.'),
            (2, 'LAB_IOT_SENSORS', 'IoT & Sensor Networks Laboratory', 'Room B-205, IIoT Wing', 'Prof. In-Charge (IoT Sensors)', 'Wireless sensor networks, gateway nodes, LoRa, cloud IoT nodes, and RF modules.'),
            (3, 'LAB_ROBOTICS', 'Robotics & Automation Laboratory', 'Room B-206, IIoT Wing', 'Prof. In-Charge (Robotics)', 'Robotic arms, motor controllers, mobile robotic chassis, and industrial automation equipment.')
        ]
        cursor.executemany('''
            INSERT INTO labs (id, lab_code, lab_name, room_no, incharge_name, description)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', default_labs)

    # Insert default users if table is empty
    from werkzeug.security import generate_password_hash
    cursor.execute('SELECT COUNT(*) FROM users')
    if cursor.fetchone()[0] == 0:
        default_users = [
            ('hod_iiot', generate_password_hash('admin123'), 'Head of Department (IIoT)', 'HOD_ADMIN', None),
            ('embedded_lab', generate_password_hash('lab123'), 'Embedded Systems Lab Assistant', 'LAB_USER', 1),
            ('iot_lab', generate_password_hash('lab123'), 'IoT & Sensors Lab Assistant', 'LAB_USER', 2),
            ('robotics_lab', generate_password_hash('lab123'), 'Robotics Lab Assistant', 'LAB_USER', 3)
        ]
        cursor.executemany('''
            INSERT INTO users (username, password_hash, display_name, role, lab_id)
            VALUES (?, ?, ?, ?, ?)
        ''', default_users)

    # Insert sample data if tables are empty
    cursor.execute('SELECT COUNT(*) FROM components')
    if cursor.fetchone()[0] == 0:
        sample_components = [
            ('RJ45 Connectors', 'Consumable', 150, 'Nos', 30, 'Rack A-1', 'Cat6 crimping connector'),
            ('Cat6 LAN Cable Roll', 'Consumable', 80, 'Meters', 20, 'Rack A-2', 'D-Link High Speed Ethernet'),
            ('CMOS Battery (CR2032)', 'Consumable', 8, 'Nos', 10, 'Drawer B-1', '3V Lithium Cell for Motherboard'),
            ('USB Optical Mouse', 'Peripherals/Hardware', 25, 'Nos', 5, 'Cupboard 1', 'Dell Wired USB Mouse'),
            ('Standard Keyboard', 'Peripherals/Hardware', 20, 'Nos', 5, 'Cupboard 1', 'HP USB Multimedia Keyboard'),
            ('HDMI to VGA Converter', 'Cables/Accessories', 6, 'Nos', 2, 'Rack C-1', 'Active converter for Projector/PC'),
            ('Thermal Paste Syringe', 'Consumable', 2, 'Nos', 2, 'Drawer B-2', 'Cooler Master CPU Grease')
        ]
        cursor.executemany('''
            INSERT INTO components (name, category, quantity, unit, min_alert_qty, rack_location, specs)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', sample_components)

    cursor.execute('SELECT COUNT(*) FROM students')
    if cursor.fetchone()[0] == 0:
        sample_students = [
            ('CO-2024-01', 'Rahul Patil', 'Computer Engineering', 'TE', 'A', '9876543210'),
            ('CO-2024-15', 'Snehal Deshmukh', 'Computer Engineering', 'TE', 'B', '9876543211'),
            ('IT-2024-08', 'Amit Shinde', 'Information Technology', 'BE', 'A', '9876543212'),
            ('AI-2024-22', 'Pooja Kadam', 'AI & Data Science', 'SE', 'A', '9876543213')
        ]
        cursor.executemany('''
            INSERT INTO students (roll_no, name, department, year, division, phone)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', sample_students)

    cursor.execute('SELECT COUNT(*) FROM faculty_staff')
    if cursor.fetchone()[0] == 0:
        sample_staff = [
            ('Prof. R. S. Kulkarni', 'EMP-101', 'Computer Engineering', 'Assistant Professor', '9822012345'),
            ('Dr. S. P. Patil', 'EMP-102', 'Information Technology', 'Associate Professor / HOD', '9423054321'),
            ('Prof. M. A. Deshmukh', 'EMP-105', 'AI & Data Science', 'Assistant Professor', '9890123456'),
            ('Mr. V. B. Shinde', 'TECH-01', 'Central Computer Facility', 'System Administrator', '9850987654')
        ]
        cursor.executemany('''
            INSERT INTO faculty_staff (name, employee_id, department, designation, phone)
            VALUES (?, ?, ?, ?, ?)
        ''', sample_staff)

    cursor.execute('SELECT COUNT(*) FROM other_labs')
    if cursor.fetchone()[0] == 0:
        sample_labs = [
            ('IoT & Embedded Systems Lab', 'Mr. S. More (Lab Tech)', '9823112233', 'Lab 204, 2nd Floor', 'Computer Engineering'),
            ('Hardware & Networking Lab', 'Mrs. P. K. Joshi', '9860445566', 'Lab 108, Ground Floor', 'Information Technology'),
            ('Project & Research Lab', 'Dr. S. P. Patil', '9423054321', 'Lab 302, 3rd Floor', 'Computer Engineering'),
            ('CAD / CAM Simulation Lab', 'Mr. A. R. Pawar', '9922778899', 'Lab 210, 2nd Floor', 'Mechanical / CCF'),
            ('AI & Machine Learning Lab', 'Prof. M. A. Deshmukh', '9890123456', 'Lab 305, 3rd Floor', 'AI & Data Science')
        ]
        cursor.executemany('''
            INSERT INTO other_labs (lab_name, incharge_name, phone, room_no, department)
            VALUES (?, ?, ?, ?, ?)
        ''', sample_labs)

    conn.commit()
    conn.close()


# ==============================================================================
# Helper Functions for Users and Multi-Lab Operations
# ==============================================================================

def get_user_by_username(username):
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE username = ? AND is_active = 1', (username,)).fetchone()
    conn.close()
    return user

def get_user_by_id(user_id):
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    return user

def get_all_labs(active_only=True):
    conn = get_db_connection()
    query = 'SELECT * FROM labs'
    if active_only:
        query += ' WHERE is_active = 1'
    query += ' ORDER BY id ASC'
    labs = conn.execute(query).fetchall()
    conn.close()
    return labs

def get_lab_by_id(lab_id):
    conn = get_db_connection()
    lab = conn.execute('SELECT * FROM labs WHERE id = ?', (lab_id,)).fetchone()
    conn.close()
    return lab

def update_lab(lab_id, lab_name, room_no, incharge_name, description=""):
    conn = get_db_connection()
    conn.execute('''
        UPDATE labs
        SET lab_name = ?, room_no = ?, incharge_name = ?, description = ?
        WHERE id = ?
    ''', (lab_name.strip(), room_no.strip(), incharge_name.strip(), description.strip(), lab_id))
    conn.commit()
    conn.close()

def create_new_lab(lab_code, lab_name, room_no, incharge_name, description, username, password):
    from werkzeug.security import generate_password_hash
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO labs (lab_code, lab_name, room_no, incharge_name, description)
        VALUES (?, ?, ?, ?, ?)
    ''', (lab_code.strip().upper(), lab_name.strip(), room_no.strip(), incharge_name.strip(), description.strip()))
    new_lab_id = cursor.lastrowid

    # Create associated user for this lab
    display_name = f"{lab_name.strip()} Assistant"
    cursor.execute('''
        INSERT INTO users (username, password_hash, display_name, role, lab_id)
        VALUES (?, ?, ?, 'LAB_USER', ?)
    ''', (username.strip().lower(), generate_password_hash(password), display_name, new_lab_id))
    conn.commit()
    conn.close()
    return new_lab_id

def reset_user_password(user_id, new_password):
    from werkzeug.security import generate_password_hash
    conn = get_db_connection()
    conn.execute('UPDATE users SET password_hash = ? WHERE id = ?', (generate_password_hash(new_password), user_id))
    conn.commit()
    conn.close()

def get_labs_with_stats():
    """Retrieve all labs with their component counts, active issues, and user details for HOD."""
    conn = get_db_connection()
    labs = conn.execute('''
        SELECT 
            l.id, l.lab_code, l.lab_name, l.room_no, l.incharge_name, l.description, l.is_active,
            u.id AS user_id, u.username, u.display_name,
            COUNT(DISTINCT c.id) AS total_components,
            COALESCE(SUM(CASE WHEN t.status = 'ISSUED' THEN 1 ELSE 0 END), 0) AS active_issues
        FROM labs l
        LEFT JOIN users u ON u.lab_id = l.id
        LEFT JOIN components c ON c.lab_id = l.id
        LEFT JOIN transactions t ON t.lab_id = l.id
        GROUP BY l.id
        ORDER BY l.id ASC
    ''').fetchall()
    conn.close()
    return labs

if __name__ == '__main__':
    init_db()
    print("Database schema updated with Multi-Lab and Users support!")
