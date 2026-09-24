-- Run only after removing duplicate "Consentimiento informado" rows for each patient.
-- Other study types may still be uploaded more than once per patient.
-- Keep the generated expression compatible with older MySQL/MariaDB versions
-- by avoiding LOWER/TRIM on the indexed expression.
ALTER TABLE studies
    ADD COLUMN consent_patient_unique_key CHAR(36)
        CHARACTER SET ascii COLLATE ascii_bin
        GENERATED ALWAYS AS (
            CASE
                WHEN study_type = 'Consentimiento informado'
                THEN patient_id
                ELSE NULL
            END
        ) STORED,
    ADD UNIQUE KEY uq_studies_one_consent_per_patient (consent_patient_unique_key);
