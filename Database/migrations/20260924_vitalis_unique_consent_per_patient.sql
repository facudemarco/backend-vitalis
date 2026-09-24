-- Run only after removing duplicate "Consentimiento informado" rows for each patient.
-- Other study types may still be uploaded more than once per patient.
-- studies.patient_id and studies.study_type use utf8mb4_unicode_ci, so the
-- generated key uses the same charset/collation as patient_id.
ALTER TABLE studies
    ADD COLUMN consent_patient_unique_key CHAR(36)
        CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        GENERATED ALWAYS AS (
            CASE
                WHEN study_type = 'Consentimiento informado'
                THEN patient_id
                ELSE NULL
            END
        ) STORED,
    ADD UNIQUE KEY uq_studies_one_consent_per_patient (consent_patient_unique_key);
