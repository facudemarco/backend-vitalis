-- Run only after removing duplicate "Consentimiento informado" rows per patient.
-- A generated column is not accepted for this expression by the current database.
-- Use a regular nullable key maintained by triggers and protected by a unique index.
-- Other study types may still be uploaded more than once per patient.

ALTER TABLE studies
    ADD COLUMN consent_patient_unique_key CHAR(36)
        CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        NULL DEFAULT NULL;

CREATE TRIGGER trg_studies_consent_key_bi
BEFORE INSERT ON studies
FOR EACH ROW
SET NEW.consent_patient_unique_key =
    IF(
        LOWER(TRIM(COALESCE(NEW.study_type, ''))) = 'consentimiento informado',
        NEW.patient_id,
        NULL
    );

CREATE TRIGGER trg_studies_consent_key_bu
BEFORE UPDATE ON studies
FOR EACH ROW
SET NEW.consent_patient_unique_key =
    IF(
        LOWER(TRIM(COALESCE(NEW.study_type, ''))) = 'consentimiento informado',
        NEW.patient_id,
        NULL
    );

UPDATE studies
SET consent_patient_unique_key =
    IF(
        LOWER(TRIM(COALESCE(study_type, ''))) = 'consentimiento informado',
        patient_id,
        NULL
    );

ALTER TABLE studies
    ADD UNIQUE KEY uq_studies_one_consent_per_patient
        (consent_patient_unique_key);
