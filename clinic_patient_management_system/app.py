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
            session['user_id'] = user['user_id']
            session['full_name'] = user['full_name']
            session['role'] = user['role']
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
@roles_required('Admin', 'Staff', 'Doctor')
def update_appointment_status(appointment_id):
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
@roles_required('Admin', 'Doctor')
def add_diagnosis():
    appointment_id = request.form.get('appointment_id') or None
    execute_query('''
        INSERT INTO diagnoses (patient_id, doctor_id, appointment_id, diagnosis, prescription, treatment_notes)
        VALUES (%s, %s, %s, %s, %s, %s)
    ''', (
        request.form['patient_id'], request.form['doctor_id'], appointment_id,
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
    user_list = fetch_all('SELECT user_id, full_name, email, role, created_at FROM users ORDER BY created_at DESC')
    return render_template('users.html', users=user_list)


@app.route('/users/add', methods=['POST'])
@login_required
@roles_required('Admin')
def add_user():
    hashed_password = generate_password_hash(request.form['password'])
    try:
        execute_query('''
            INSERT INTO users (full_name, email, password, role)
            VALUES (%s, %s, %s, %s)
        ''', (request.form['full_name'], request.form['email'], hashed_password, request.form['role']))
        flash('User account created successfully.', 'success')
    except Error:
        flash('Email already exists or invalid input.', 'danger')
    return redirect(url_for('users'))


@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


if __name__ == '__main__':
    app.run(debug=True)
