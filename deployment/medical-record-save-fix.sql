-- Ejecutar manualmente en MariaDB antes de desplegar. No modifica fichas existentes.
ALTER TABLE medical_record_data
    ADD COLUMN IF NOT EXISTS education_level VARCHAR(20) NULL,
    ADD COLUMN IF NOT EXISTS sector VARCHAR(255) NULL;

-- Los teléfonos de diez o más dígitos pueden superar el máximo de INT firmado.
ALTER TABLE medical_record_data MODIFY COLUMN phone BIGINT NULL;
