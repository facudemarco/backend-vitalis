-- Vitalis medical record fields requested on 2026-09-24.
-- Run once against the Hostinger MySQL database before deploying the backend.
ALTER TABLE medical_record_surgerys
    ADD COLUMN others_description TEXT NULL;

ALTER TABLE medical_record_studies
    ADD COLUMN examen_fisico TINYINT(1) NULL DEFAULT NULL;
