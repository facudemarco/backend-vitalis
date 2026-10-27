-- MariaDB: ejecutar manualmente antes de desplegar el backend/frontend.
-- Conserva las fichas existentes sin inventar un nivel de estudios o sector.
ALTER TABLE medical_record_data
    ADD COLUMN IF NOT EXISTS education_level VARCHAR(20) NULL,
    ADD COLUMN IF NOT EXISTS sector VARCHAR(255) NULL;

ALTER TABLE medical_record_data MODIFY COLUMN phone BIGINT NULL;
