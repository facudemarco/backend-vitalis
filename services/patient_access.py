from fastapi import HTTPException
from sqlalchemy import text


def studies_ready_condition(patient_reference):
    """Shared SQL predicate for publication and the manual completion guard."""
    return f"""
        EXISTS (SELECT 1 FROM studies s WHERE s.patient_id = {patient_reference})
        AND NOT EXISTS (
            SELECT 1 FROM studies s
            WHERE s.patient_id = {patient_reference}
              AND (
                COALESCE(s.status, '') <> 'Disponible'
                OR NOT EXISTS (SELECT 1 FROM study_files sf WHERE sf.study_id = s.id AND sf.is_report = 0)
                OR (
                    LOWER(TRIM(s.study_type)) <> 'consentimiento informado'
                    AND COALESCE((
                        SELECT sa.requires_report FROM studies_admin sa
                        WHERE LOWER(TRIM(sa.name)) = LOWER(TRIM(s.study_type)) LIMIT 1
                    ), 1) = 1
                    AND NOT EXISTS (SELECT 1 FROM study_files sf WHERE sf.study_id = s.id AND sf.is_report = 1)
                )
              )
        )
    """


def studies_are_ready(db, patient_id):
    return bool(db.execute(
        text("SELECT " + studies_ready_condition(":pid")),
        {"pid": patient_id},
    ).scalar())


def require_patient_access(db, current_user, patient_id):
    """Companies only receive employees explicitly released by clinic staff."""
    patient = db.execute(
        text("SELECT id, company_id, user_id, patient_status FROM patients WHERE id = :pid"),
        {"pid": patient_id},
    ).mappings().first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    if current_user.role in ("admin", "secretary", "professional"):
        return patient
    if current_user.role == "patient" and patient["user_id"] == current_user.id:
        return patient
    if current_user.role == "company":
        company = db.execute(
            text("SELECT id FROM companies WHERE owner_user_id = :uid"),
            {"uid": current_user.id},
        ).mappings().first()
        if (company and patient["company_id"] == company["id"]
                and patient["patient_status"] == "Completado"):
            return patient
        # Do not reveal whether an unpublished or another company's patient exists.
        raise HTTPException(status_code=404, detail="Patient not found")
    raise HTTPException(status_code=403, detail="Access denied")
