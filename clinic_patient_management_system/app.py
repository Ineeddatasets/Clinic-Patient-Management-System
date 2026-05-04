import os
from functools import wraps
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector
from mysql.connector import Error

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'dev-secret-key')


def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        user=os.getenv('DB_USER', 'root'),
        password=os.getenv('DB_PASSWORD', ''),
        database=os.getenv('DB_NAME', 'clinic_management_db'),
        port=int(os.getenv('DB_PORT', 3306))
    )


def fetch_all(query, params=None):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(query, params or ())
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows


def fetch_one(query, params=None):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(query, params or ())
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return row


def execute_query(query, params=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(query, params or ())
    conn.commit()
    cursor.close()
    conn.close()


def execute_insert(query, params=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(query, params or ())
    conn.commit()
    last_id = cursor.lastrowid
    cursor.close()
    conn.close()
    return last_id


def ensure_doctor_profile_for_user(user):
    """Automatically creates/connects a doctor profile for a Doctor user account."""
    if not user or user.get('role') != 'Doctor' or user.get('doctor_id'):
        return user

    existing_doctor = fetch_one('SELECT doctor_id FROM doctors WHERE email=%s', (user['email'],))
    if existing_doctor:
        doctor_id = existing_doctor['doctor_id']
    else:
        doctor_id = execute_insert("""
            INSERT INTO doctors (full_name, specialization, contact_number, email)
            VALUES (%s, %s, %s, %s)
        """, (user['full_name'], '', '', user['email']))

    execute_query('UPDATE users SET doctor_id=%s WHERE user_id=%s', (doctor_id, user['user_id']))
    user['doctor_id'] = doctor_id
    return user


def repair_unlinked_doctor_accounts():
    """Auto-fixes old Doctor accounts created before doctor-profile linking existed."""
    unlinked_doctors = fetch_all("""
        SELECT user_id, full_name, email, role, doctor_id
        FROM users
        WHERE role='Doctor' AND doctor_id IS NULL
    """)
    repaired = 0
    for user in unlinked_doctors:
        ensure_doctor_profile_for_user(user)
        repaired += 1
    return repaired


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login first.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def roles_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if session.get('role') not in roles:
                flash('You are not allowed to access that page.', 'danger')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator


@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = fetch_one('SELECT * FROM users WHERE email=%s', (email,))

        if user and check_password_hash(user['password'], password):
            user = ensure_doctor_profile_for_user(user)
            session['user_id'] = user['user_id']
            session['full_name'] = user['full_name']
            session['role'] = user['role']
            session['doctor_id'] = user.get('doctor_id')
            flash('Login successful.', 'success')
            return redirect(url_for('dashboard'))

        flash('Invalid email or password.', 'danger')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))


@app.route('/dashboard')
@login_required
def dashboard():
    if session.get('role') == 'Doctor':
        doctor_id = session.get('doctor_id')
        if not doctor_id:
            stats = {'patients': 0, 'doctors': 1, 'appointments': 0, 'pending': 0, 'diagnoses': 0}
            recent_appointments = []
            flash('Your doctor account is not linked to a doctor profile yet. Please contact the admin.', 'warning')
        else:
            stats = {
                'patients': fetch_one('''
                    SELECT COUNT(DISTINCT patient_id) AS total FROM appointments WHERE doctor_id=%s
                ''', (doctor_id,))['total'],
                'doctors': 1,
                'appointments': fetch_one('SELECT COUNT(*) AS total FROM appointments WHERE doctor_id=%s', (doctor_id,))['total'],
                'pending': fetch_one("SELECT COUNT(*) AS total FROM appointments WHERE status='Pending' AND doctor_id=%s", (doctor_id,))['total'],
                'diagnoses': fetch_one('SELECT COUNT(*) AS total FROM diagnoses WHERE doctor_id=%s', (doctor_id,))['total']
            }
            recent_appointments = fetch_all('''
                SELECT a.*, p.full_name AS patient_name, d.full_name AS doctor_name
                FROM appointments a
                JOIN patients p ON a.patient_id = p.patient_id
                JOIN doctors d ON a.doctor_id = d.doctor_id
                WHERE a.doctor_id=%s
                ORDER BY a.created_at DESC LIMIT 5
            ''', (doctor_id,))
    else:
        stats = {
            'patients': fetch_one('SELECT COUNT(*) AS total FROM patients')['total'],
            'doctors': fetch_one('SELECT COUNT(*) AS total FROM doctors')['total'],
            'appointments': fetch_one('SELECT COUNT(*) AS total FROM appointments')['total'],
            'pending': fetch_one("SELECT COUNT(*) AS total FROM appointments WHERE status='Pending'")['total'],
            'diagnoses': fetch_one('SELECT COUNT(*) AS total FROM diagnoses')['total']
        }
        recent_appointments = fetch_all('''
            SELECT a.*, p.full_name AS patient_name, d.full_name AS doctor_name
            FROM appointments a
            JOIN patients p ON a.patient_id = p.patient_id
            JOIN doctors d ON a.doctor_id = d.doctor_id
            ORDER BY a.created_at DESC LIMIT 5
        ''')
    return render_template('dashboard.html', stats=stats, recent_appointments=recent_appointments)


@app.route('/patients')
@login_required
@roles_required('Admin', 'Staff')
def patients():
    search = request.args.get('search', '')
    if search:
        patient_list = fetch_all('''
            SELECT * FROM patients
            WHERE full_name LIKE %s OR contact_number LIKE %s OR address LIKE %s
            ORDER BY date_registered DESC
        ''', (f'%{search}%', f'%{search}%', f'%{search}%'))
    else:
        patient_list = fetch_all('SELECT * FROM patients ORDER BY date_registered DESC')
    return render_template('patients.html', patients=patient_list, search=search)


@app.route('/patients/add', methods=['POST'])
@login_required
@roles_required('Admin', 'Staff')
def add_patient():
    execute_query('''
        INSERT INTO patients (full_name, age, gender, address, contact_number, medical_history)
        VALUES (%s, %s, %s, %s, %s, %s)
    ''', (
        request.form['full_name'], request.form['age'], request.form['gender'],
        request.form['address'], request.form['contact_number'], request.form['medical_history']
    ))
    flash('Patient added successfully.', 'success')
    return redirect(url_for('patients'))


@app.route('/patients/edit/<int:patient_id>', methods=['POST'])
@login_required
@roles_required('Admin', 'Staff')
def edit_patient(patient_id):
    execute_query('''
        UPDATE patients SET full_name=%s, age=%s, gender=%s, address=%s, contact_number=%s, medical_history=%s
        WHERE patient_id=%s
    ''', (
        request.form['full_name'], request.form['age'], request.form['gender'],
        request.form['address'], request.form['contact_number'], request.form['medical_history'], patient_id
    ))
    flash('Patient updated successfully.', 'success')
    return redirect(url_for('patients'))


@app.route('/patients/delete/<int:patient_id>')
@login_required
@roles_required('Admin', 'Staff')
def delete_patient(patient_id):
    execute_query('DELETE FROM patients WHERE patient_id=%s', (patient_id,))
    flash('Patient deleted successfully.', 'success')
    return redirect(url_for('patients'))


@app.route('/appointments')
@login_required
def appointments():
    if session.get('role') == 'Doctor':
        doctor_id = session.get('doctor_id')
        if not doctor_id:
            appointment_list = []
            flash('Your doctor account is not linked to a doctor profile yet. Please contact the admin.', 'warning')
        else:
            appointment_list = fetch_all('''
                SELECT a.*, p.full_name AS patient_name, d.full_name AS doctor_name
                FROM appointments a
                JOIN patients p ON a.patient_id = p.patient_id
                JOIN doctors d ON a.doctor_id = d.doctor_id
                WHERE a.doctor_id=%s
                ORDER BY a.appointment_date DESC, a.appointment_time DESC
            ''', (doctor_id,))
    else:
        appointment_list = fetch_all('''
            SELECT a.*, p.full_name AS patient_name, d.full_name AS doctor_name
            FROM appointments a
            JOIN patients p ON a.patient_id = p.patient_id
            JOIN doctors d ON a.doctor_id = d.doctor_id
            ORDER BY a.appointment_date DESC, a.appointment_time DESC
        ''')
    patient_list = fetch_all('SELECT patient_id, full_name FROM patients ORDER BY full_name')
    doctor_list = fetch_all('SELECT doctor_id, full_name FROM doctors ORDER BY full_name')
    return render_template('appointments.html', appointments=appointment_list, patients=patient_list, doctors=doctor_list)


@app.route('/appointments/add', methods=['POST'])
@login_required
@roles_required('Admin', 'Staff')
def add_appointment():
    execute_query('''
        INSERT INTO appointments (patient_id, doctor_id, appointment_date, appointment_time, reason)
        VALUES (%s, %s, %s, %s, %s)
    ''', (
        request.form['patient_id'], request.form['doctor_id'], request.form['appointment_date'],
        request.form['appointment_time'], request.form['reason']
    ))
    flash('Appointment created successfully.', 'success')
    return redirect(url_for('appointments'))


@app.route('/appointments/status/<int:appointment_id>', methods=['POST'])
@login_required
@roles_required('Admin', 'Doctor')
def update_appointment_status(appointment_id):
    appointment = fetch_one('SELECT doctor_id FROM appointments WHERE appointment_id=%s', (appointment_id,))
    if not appointment:
        flash('Appointment not found.', 'danger')
        return redirect(url_for('appointments'))

    if session.get('role') == 'Doctor' and appointment['doctor_id'] != session.get('doctor_id'):
        flash('You can only update appointments assigned to your own doctor account.', 'danger')
        return redirect(url_for('appointments'))

    execute_query('UPDATE appointments SET status=%s WHERE appointment_id=%s', (request.form['status'], appointment_id))
    flash('Appointment status updated.', 'success')
    return redirect(url_for('appointments'))


@app.route('/doctors')
@login_required
@roles_required('Admin')
def doctors():
    doctor_list = fetch_all('SELECT * FROM doctors ORDER BY full_name')
    return render_template('doctors.html', doctors=doctor_list)


@app.route('/doctors/add', methods=['POST'])
@login_required
@roles_required('Admin')
def add_doctor():
    execute_query('''
        INSERT INTO doctors (full_name, specialization, contact_number, email)
        VALUES (%s, %s, %s, %s)
    ''', (request.form['full_name'], request.form['specialization'], request.form['contact_number'], request.form['email']))
    flash('Doctor added successfully.', 'success')
    return redirect(url_for('doctors'))


@app.route('/doctors/delete/<int:doctor_id>')
@login_required
@roles_required('Admin')
def delete_doctor(doctor_id):
    execute_query('DELETE FROM doctors WHERE doctor_id=%s', (doctor_id,))
    flash('Doctor deleted successfully.', 'success')
    return redirect(url_for('doctors'))


@app.route('/diagnoses')
@login_required
@roles_required('Admin', 'Doctor')
def diagnoses():
    if session.get('role') == 'Doctor':
        doctor_id = session.get('doctor_id')
        if not doctor_id:
            diagnosis_list = []
            patient_list = []
            doctor_list = []
            appointment_list = []
            flash('Your doctor account is not linked to a doctor profile yet. Please contact the admin.', 'warning')
        else:
            diagnosis_list = fetch_all('''
                SELECT dg.*, p.full_name AS patient_name, d.full_name AS doctor_name
                FROM diagnoses dg
                JOIN patients p ON dg.patient_id = p.patient_id
                JOIN doctors d ON dg.doctor_id = d.doctor_id
                WHERE dg.doctor_id=%s
                ORDER BY dg.diagnosis_date DESC
            ''', (doctor_id,))
            patient_list = fetch_all('''
                SELECT DISTINCT p.patient_id, p.full_name
                FROM patients p
                JOIN appointments a ON p.patient_id = a.patient_id
                WHERE a.doctor_id=%s
                ORDER BY p.full_name
            ''', (doctor_id,))
            doctor_list = fetch_all('SELECT doctor_id, full_name FROM doctors WHERE doctor_id=%s', (doctor_id,))
            appointment_list = fetch_all('''
                SELECT a.appointment_id, p.full_name AS patient_name, a.appointment_date, a.appointment_time
                FROM appointments a JOIN patients p ON a.patient_id = p.patient_id
                WHERE a.doctor_id=%s
                ORDER BY a.appointment_date DESC
            ''', (doctor_id,))
    else:
        diagnosis_list = fetch_all('''
            SELECT dg.*, p.full_name AS patient_name, d.full_name AS doctor_name
            FROM diagnoses dg
            JOIN patients p ON dg.patient_id = p.patient_id
            JOIN doctors d ON dg.doctor_id = d.doctor_id
            ORDER BY dg.diagnosis_date DESC
        ''')
        patient_list = fetch_all('SELECT patient_id, full_name FROM patients ORDER BY full_name')
        doctor_list = fetch_all('SELECT doctor_id, full_name FROM doctors ORDER BY full_name')
        appointment_list = fetch_all('''
            SELECT a.appointment_id, p.full_name AS patient_name, a.appointment_date, a.appointment_time
            FROM appointments a JOIN patients p ON a.patient_id = p.patient_id
            ORDER BY a.appointment_date DESC
        ''')
    return render_template('diagnoses.html', diagnoses=diagnosis_list, patients=patient_list, doctors=doctor_list, appointments=appointment_list)


@app.route('/diagnoses/add', methods=['POST'])
@login_required
@roles_required('Doctor')
def add_diagnosis():
    appointment_id = request.form.get('appointment_id') or None
    patient_id = request.form['patient_id']

    doctor_id = session.get('doctor_id')
    if not doctor_id:
        flash('Your doctor account is not linked to a doctor profile yet.', 'danger')
        return redirect(url_for('diagnoses'))

    if appointment_id:
        appointment = fetch_one('SELECT patient_id, doctor_id FROM appointments WHERE appointment_id=%s', (appointment_id,))
        if not appointment or appointment['doctor_id'] != doctor_id:
            flash('You can only add diagnosis for appointments assigned to you.', 'danger')
            return redirect(url_for('diagnoses'))
        patient_id = appointment['patient_id']

    execute_query('''
        INSERT INTO diagnoses (patient_id, doctor_id, appointment_id, diagnosis, prescription, treatment_notes)
        VALUES (%s, %s, %s, %s, %s, %s)
    ''', (
        patient_id, doctor_id, appointment_id,
        request.form['diagnosis'], request.form['prescription'], request.form['treatment_notes']
    ))
    if appointment_id:
        execute_query("UPDATE appointments SET status='Completed' WHERE appointment_id=%s", (appointment_id,))
    flash('Diagnosis record saved successfully.', 'success')
    return redirect(url_for('diagnoses'))


@app.route('/reports')
@login_required
@roles_required('Admin')
def reports():
    status_report = fetch_all('SELECT status, COUNT(*) AS total FROM appointments GROUP BY status')
    monthly_report = fetch_all('''
        SELECT DATE_FORMAT(appointment_date, '%Y-%m') AS month, COUNT(*) AS total
        FROM appointments GROUP BY month ORDER BY month DESC
    ''')
    diagnosis_report = fetch_all('''
        SELECT DATE(diagnosis_date) AS date, COUNT(*) AS total
        FROM diagnoses GROUP BY DATE(diagnosis_date) ORDER BY date DESC LIMIT 10
    ''')
    return render_template('reports.html', status_report=status_report, monthly_report=monthly_report, diagnosis_report=diagnosis_report)


@app.route('/users')
@login_required
@roles_required('Admin')
def users():
    repaired = repair_unlinked_doctor_accounts()
    if repaired:
        flash(f'{repaired} old doctor account(s) were automatically connected to their own doctor profile.', 'info')

    user_list = fetch_all('''
        SELECT u.user_id, u.full_name, u.email, u.role, u.doctor_id, u.created_at, d.full_name AS doctor_name
        FROM users u
        LEFT JOIN doctors d ON u.doctor_id = d.doctor_id
        ORDER BY u.created_at DESC
    ''')
    return render_template('users.html', users=user_list)


@app.route('/users/add', methods=['POST'])
@login_required
@roles_required('Admin')
def add_user():
    full_name = request.form['full_name'].strip()
    email = request.form['email'].strip()
    hashed_password = generate_password_hash(request.form['password'])
    role = request.form['role']
    doctor_id = None

    try:
        if role == 'Doctor':
            # A Doctor user account must have its own doctor profile.
            # If a matching doctor profile already exists by email, reuse it.
            # Otherwise, automatically create a new doctor profile for this account.
            existing_doctor = fetch_one('SELECT doctor_id FROM doctors WHERE email=%s', (email,))
            if existing_doctor:
                doctor_id = existing_doctor['doctor_id']
            else:
                doctor_id = execute_insert('''
                    INSERT INTO doctors (full_name, specialization, contact_number, email)
                    VALUES (%s, %s, %s, %s)
                ''', (
                    full_name,
                    request.form.get('specialization', '').strip(),
                    request.form.get('contact_number', '').strip(),
                    email
                ))

        execute_query('''
            INSERT INTO users (full_name, email, password, role, doctor_id)
            VALUES (%s, %s, %s, %s, %s)
        ''', (full_name, email, hashed_password, role, doctor_id))

        if role == 'Doctor':
            flash('Doctor account created and automatically connected to its own doctor profile.', 'success')
        else:
            flash('User account created successfully.', 'success')
    except Error as e:
        flash(f'Email already exists or invalid input. Details: {e}', 'danger')
    return redirect(url_for('users'))


@app.route('/users/link-doctor/<int:user_id>', methods=['POST'])
@login_required
@roles_required('Admin')
def link_doctor_account(user_id):
    flash('Manual doctor linking was removed. Doctor accounts are now connected automatically.', 'info')
    return redirect(url_for('users'))


@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


if __name__ == '__main__':
    app.run(debug=True)
