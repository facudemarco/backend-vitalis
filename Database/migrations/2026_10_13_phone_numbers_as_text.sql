-- Convert phone columns to text so leading zeros, plus signs, and formatting are preserved.
-- Apply once to the target MariaDB database before deploying the phone-form changes.
ALTER TABLE patients
    MODIFY COLUMN phone VARCHAR(50) NULL;

ALTER TABLE companies
    MODIFY COLUMN phone VARCHAR(50) NULL;

ALTER TABLE users
    MODIFY COLUMN phone VARCHAR(50) NULL;
