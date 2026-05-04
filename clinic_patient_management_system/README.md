# Clinic Patient Management System

Backend: Python Flask  
Frontend: HTML and CSS  
Database: MySQL

## Modules
1. Patient Registration Module
2. Appointment Scheduling Module
3. Doctor/Diagnosis Module
4. Admin and Reports Module

## How to Run Locally

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Create MySQL database and import:
```bash
mysql -u root -p < database/clinic_management_db.sql
```

3. Copy `.env.example` to `.env` and update your MySQL details.

4. Run the system:
```bash
python app.py
```

5. Open:
```text
http://127.0.0.1:5000
```

## Default Accounts

Admin:
- Email: admin@clinic.com
- Password: admin123

Staff:
- Email: staff@clinic.com
- Password: staff123

Doctor:
- Email: doctor@clinic.com
- Password: doctor123

## Hosting Notes
Use Railway, Render, or PythonAnywhere. Add the same environment variables from `.env.example` to your hosting provider.
