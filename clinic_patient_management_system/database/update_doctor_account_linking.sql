-- Run this once in your local database and once in Railway database.
-- Local phpMyAdmin: select clinic_management_db first.
-- Railway MySQL Workbench: run USE railway; first.

ALTER TABLE users ADD COLUMN doctor_id INT NULL;

-- Optional: connect existing doctor accounts to doctor profiles when the email matches.
UPDATE users u
JOIN doctors d ON u.email = d.email
SET u.doctor_id = d.doctor_id
WHERE u.role = 'Doctor' AND u.doctor_id IS NULL;
