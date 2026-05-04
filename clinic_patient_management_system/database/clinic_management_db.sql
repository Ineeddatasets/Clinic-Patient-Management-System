CREATE DATABASE IF NOT EXISTS clinic_management_db;
USE clinic_management_db;

DROP TABLE IF EXISTS diagnoses;
DROP TABLE IF EXISTS appointments;
DROP TABLE IF EXISTS doctors;
DROP TABLE IF EXISTS patients;
DROP TABLE IF EXISTS users;

CREATE TABLE users (
    user_id INT AUTO_INCREMENT PRIMARY KEY,
    full_name VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    role ENUM('Admin', 'Staff', 'Doctor') NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE patients (
    patient_id INT AUTO_INCREMENT PRIMARY KEY,
    full_name VARCHAR(100) NOT NULL,
    age INT NOT NULL,
    gender VARCHAR(20),
    address TEXT,
    contact_number VARCHAR(20),
    medical_history TEXT,
    date_registered TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE doctors (
    doctor_id INT AUTO_INCREMENT PRIMARY KEY,
    full_name VARCHAR(100) NOT NULL,
    specialization VARCHAR(100),
    contact_number VARCHAR(20),
    email VARCHAR(100)
);

CREATE TABLE appointments (
    appointment_id INT AUTO_INCREMENT PRIMARY KEY,
    patient_id INT NOT NULL,
    doctor_id INT NOT NULL,
    appointment_date DATE NOT NULL,
    appointment_time TIME NOT NULL,
    status ENUM('Pending', 'Approved', 'Completed', 'Cancelled') DEFAULT 'Pending',
    reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES patients(patient_id) ON DELETE CASCADE,
    FOREIGN KEY (doctor_id) REFERENCES doctors(doctor_id) ON DELETE CASCADE
);

CREATE TABLE diagnoses (
    diagnosis_id INT AUTO_INCREMENT PRIMARY KEY,
    patient_id INT NOT NULL,
    doctor_id INT NOT NULL,
    appointment_id INT NULL,
    diagnosis TEXT NOT NULL,
    prescription TEXT,
    treatment_notes TEXT,
    diagnosis_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES patients(patient_id) ON DELETE CASCADE,
    FOREIGN KEY (doctor_id) REFERENCES doctors(doctor_id) ON DELETE CASCADE,
    FOREIGN KEY (appointment_id) REFERENCES appointments(appointment_id) ON DELETE SET NULL
);

INSERT INTO users (full_name, email, password, role) VALUES
('System Administrator', 'admin@clinic.com', 'pbkdf2:sha256:1000000$c2ded0c5e8c8531d$fdb43bd5f8b510fee77b1f76a8e9daf0a29ce0570a83fce08dce4f92b48fa2fe', 'Admin'),
('Clinic Staff', 'staff@clinic.com', 'pbkdf2:sha256:1000000$ee449504a8335d78$51418d9227de429d32ee637791a65a82a5ef147582a9ee4293ecf596b9f261d0', 'Staff'),
('Clinic Doctor', 'doctor@clinic.com', 'pbkdf2:sha256:1000000$b3619efa2fa72f46$108b306e3e0ef0714a95c2587aceef5818d84c72839e69d82edcd3174da9a635', 'Doctor');

INSERT INTO doctors (full_name, specialization, contact_number, email) VALUES
('Dr. Maria Santos', 'General Medicine', '09123456789', 'maria.santos@clinic.com'),
('Dr. Juan Dela Cruz', 'Family Medicine', '09987654321', 'juan.delacruz@clinic.com');

INSERT INTO patients (full_name, age, gender, address, contact_number, medical_history) VALUES
('John Doe', 25, 'Male', 'Cebu City', '09111111111', 'No major medical history'),
('Jane Smith', 31, 'Female', 'Mandaue City', '09222222222', 'Asthma');
