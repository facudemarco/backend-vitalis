from fastapi import APIRouter, Depends, HTTPException, status, Form
from models.user import UserSchema
from auth.authentication import require_active_user, require_roles
from Database.getConnection import getConnectionForLogin
from sqlalchemy import text
from datetime import datetime
import uuid
from typing import Optional, Any
from models.user import User

router = APIRouter(prefix="/medical-records", tags=["Medical Records"])

def _get_professional_id(db, user_id: str) -> str:
    row = db.execute(
        text("SELECT id FROM professionals WHERE user_id = :uid LIMIT 1"),
        {"uid": user_id}
    ).mappings().first()
    if not row:
        raise HTTPException(status_code=400, detail="User is not a professional")
    return row["id"]

def _get_patient_company_id(db, patient_id: str) -> Optional[str]:
    row = db.execute(
        text("SELECT company_id FROM patients WHERE id = :pid LIMIT 1"),
        {"pid": patient_id}
    ).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Patient not found")
    return row["company_id"]

def _check_record_access(current_user: UserSchema, record_id: str, db) -> dict:
    row = db.execute(
        text("SELECT id, patient_id, company_id, created_by_user_id FROM medical_records WHERE id = :rid"),
        {"rid": record_id}
    ).mappings().first()
    
    if not row:
        raise HTTPException(status_code=404, detail="Medical record not found")
    
    if current_user.role == "admin":
        return row
    
    if current_user.role == "professional":
        return row
    
    if current_user.role == "company":
        company_row = db.execute(
            text("SELECT id FROM companies WHERE owner_user_id = :uid"),
            {"uid": current_user.id}
        ).mappings().first()
        if not company_row or row["company_id"] != company_row["id"]:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return row
    
    if current_user.role == "patient":
        patient_row = db.execute(
            text("SELECT user_id FROM patients WHERE id = :pid"),
            {"pid": row["patient_id"]}
        ).mappings().first()
        if not patient_row or patient_row["user_id"] != current_user.id:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return row
    
    raise HTTPException(status_code=403, detail="Insufficient permissions")

def _format_medical_record(row) -> dict:
    return {
        "id": row["id"],
        "patient_id": row["patient_id"],
        "company_id": row["company_id"],
        "professional_id": row["professional_id"],
        "exam_date": row["exam_date"],
        "evaluation_type": row["evaluation_type"],
        "evaluation_type_other": row.get("evaluation_type_other"),
        "civil_status": row.get("civil_status"),
        "job_tasks": row.get("job_tasks"),
        "sector": row.get("sector"),
        "education_level": row.get("education_level"),
        "general_observations": row.get("general_observations"),
        "fitness_result": row.get("fitness_result"),
        "fitness_duration": row.get("fitness_duration"),
        "fitness_observations": row.get("fitness_observations"),
        "referrals": row.get("referrals"),
        "created_by_user_id": row["created_by_user_id"],
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }

@router.post("/patient/{patient_id}", tags=["Medical Records - Cabecera"])
async def create_medical_record(
    patient_id: str,
    exam_date: str = Form(...),
    evaluation_type: str = Form(default=""),
    evaluation_type_other: str = Form(default=""),
    civil_status: str = Form(default=""),
    job_tasks: str = Form(default=""),
    sector: str = Form(default=""),
    education_level: str = Form(default=""),
    general_observations: str = Form(default=""),
    fitness_result: str = Form(default=""),
    fitness_duration: str = Form(default=""),
    fitness_observations: str = Form(default=""),
    referrals: str = Form(default=""),
    current_user: UserSchema = Depends(require_roles("professional", "admin"))
):
    """A.1) Crear historial médico para un paciente"""
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        patient = db.execute(
            text("SELECT id, company_id FROM patients WHERE id = :pid"),
            {"pid": patient_id}
        ).mappings().first()
        
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")
        
        # Obtener professional_id
        if current_user.role == "professional":
            professional_id = _get_professional_id(db, current_user.id)
        else:  # admin
            professional_id = None
        
        # Crear record
        record_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        
        db.execute(text("""
            INSERT INTO medical_records 
            (id, patient_id, company_id, professional_id, exam_date, evaluation_type, 
             evaluation_type_other, civil_status, job_tasks, sector, education_level, 
             general_observations, fitness_result, fitness_duration, fitness_observations, 
             referrals, created_by_user_id, created_at, updated_at)
            VALUES 
            (:id, :patient_id, :company_id, :professional_id, :exam_date, :evaluation_type,
             :evaluation_type_other, :civil_status, :job_tasks, :sector, :education_level,
             :general_observations, :fitness_result, :fitness_duration, :fitness_observations,
             :referrals, :created_by_user_id, :created_at, :updated_at)
        """), {
            "id": record_id,
            "patient_id": patient_id,
            "company_id": patient["company_id"],
            "professional_id": professional_id,
            "exam_date": exam_date,
            "evaluation_type": evaluation_type,
            "evaluation_type_other": evaluation_type_other,
            "civil_status": civil_status,
            "job_tasks": job_tasks,
            "sector": sector,
            "education_level": education_level,
            "general_observations": general_observations,
            "fitness_result": fitness_result,
            "fitness_duration": fitness_duration,
            "fitness_observations": fitness_observations,
            "referrals": referrals,
            "created_by_user_id": current_user.id,
            "created_at": now,
            "updated_at": now,
        })
        
        db.commit()
        
        return {
            "detail": "Medical record created successfully",
            "record_id": record_id,
            "patient_id": patient_id,
            "exam_date": exam_date,
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail="Error creating medical record")
    finally:
        db.close()


@router.get("/patient/{patient_id}", tags=["Medical Records - Cabecera"])
async def get_patient_medical_records(
    patient_id: str,
    current_user: UserSchema = Depends(require_active_user)
):
    """A.2) Listar historiales de un paciente (ordenado DESC)"""
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        # Validar acceso
        patient = db.execute(
            text("SELECT id, company_id, user_id FROM patients WHERE id = :pid"),
            {"pid": patient_id}
        ).mappings().first()
        
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")
        
        # Verificar permisos
        if current_user.role == "patient":
            if patient["user_id"] != current_user.id:
                raise HTTPException(status_code=403, detail="You can only view your own records")
        elif current_user.role == "company":
            company = db.execute(
                text("SELECT id FROM companies WHERE owner_user_id = :uid"),
                {"uid": current_user.id}
            ).mappings().first()
            if not company or patient["company_id"] != company["id"]:
                raise HTTPException(status_code=403, detail="You can only view your employees' records")
        elif current_user.role not in ("admin", "professional"):
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        
        # Obtener records
        rows = db.execute(
            text("""
                SELECT id, patient_id, company_id, professional_id, exam_date, 
                       evaluation_type, evaluation_type_other, civil_status, job_tasks, 
                       sector, education_level, general_observations, fitness_result, 
                       fitness_duration, fitness_observations, referrals, 
                       created_by_user_id, created_at, updated_at
                FROM medical_records
                WHERE patient_id = :pid
                ORDER BY created_at DESC
            """),
            {"pid": patient_id}
        ).mappings().all()
        
        records = [_format_medical_record(row) for row in rows]
        return {"patient_id": patient_id, "records": records, "total": len(records)}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error fetching medical records")
    finally:
        db.close()


@router.get("/{record_id}", tags=["Medical Records - Cabecera"])
async def get_medical_record(record_id: str, current_user: UserSchema = Depends(require_active_user)):
    """A.3) Obtener un historial por ID"""
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        _check_record_access(current_user, record_id, db)
        
        row = db.execute(
            text("""
                SELECT id, patient_id, company_id, professional_id, exam_date, 
                       evaluation_type, evaluation_type_other, civil_status, job_tasks, 
                       sector, education_level, general_observations, fitness_result, 
                       fitness_duration, fitness_observations, referrals, 
                       created_by_user_id, created_at, updated_at
                FROM medical_records
                WHERE id = :rid
            """),
            {"rid": record_id}
        ).mappings().first()
        
        if not row:
            raise HTTPException(status_code=404, detail="Medical record not found")
        
        return _format_medical_record(row)
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error fetching medical record")
    finally:
        db.close()


@router.patch("/{record_id}", tags=["Medical Records - Cabecera"])
async def update_medical_record(
    record_id: str,
    evaluation_type: str = Form(default=None),
    evaluation_type_other: str = Form(default=None),
    civil_status: str = Form(default=None),
    job_tasks: str = Form(default=None),
    sector: str = Form(default=None),
    education_level: str = Form(default=None),
    general_observations: str = Form(default=None),
    fitness_result: str = Form(default=None),
    fitness_duration: str = Form(default=None),
    fitness_observations: str = Form(default=None),
    referrals: str = Form(default=None),
    current_user: UserSchema = Depends(require_roles("professional", "admin"))
):
    """A.4) Editar cabecera del historial"""
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        row = db.execute(
            text("SELECT id, created_by_user_id FROM medical_records WHERE id = :rid"),
            {"rid": record_id}
        ).mappings().first()
        
        if not row:
            raise HTTPException(status_code=404, detail="Medical record not found")
        
        # Verificar permisos
        if current_user.role != "admin" and row["created_by_user_id"] != current_user.id:
            raise HTTPException(status_code=403, detail="You can only modify your own records")
        
        # Actualizar solo campos no-None
        now = datetime.utcnow().isoformat()
        updates = []
        params = {"rid": record_id}
        
        if evaluation_type is not None:
            updates.append("evaluation_type = :evaluation_type")
            params["evaluation_type"] = evaluation_type
        if evaluation_type_other is not None:
            updates.append("evaluation_type_other = :evaluation_type_other")
            params["evaluation_type_other"] = evaluation_type_other
        if civil_status is not None:
            updates.append("civil_status = :civil_status")
            params["civil_status"] = civil_status
        if job_tasks is not None:
            updates.append("job_tasks = :job_tasks")
            params["job_tasks"] = job_tasks
        if sector is not None:
            updates.append("sector = :sector")
            params["sector"] = sector
        if education_level is not None:
            updates.append("education_level = :education_level")
            params["education_level"] = education_level
        if general_observations is not None:
            updates.append("general_observations = :general_observations")
            params["general_observations"] = general_observations
        if fitness_result is not None:
            updates.append("fitness_result = :fitness_result")
            params["fitness_result"] = fitness_result
        if fitness_duration is not None:
            updates.append("fitness_duration = :fitness_duration")
            params["fitness_duration"] = fitness_duration
        if fitness_observations is not None:
            updates.append("fitness_observations = :fitness_observations")
            params["fitness_observations"] = fitness_observations
        if referrals is not None:
            updates.append("referrals = :referrals")
            params["referrals"] = referrals
        
        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")
        
        updates.append("updated_at = :updated_at")
        params["updated_at"] = now
        
        db.execute(
            text(f"UPDATE medical_records SET {', '.join(updates)} WHERE id = :rid"),
            params
        )
        db.commit()
        
        return {"detail": "Medical record updated successfully", "record_id": record_id}
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Error updating medical record")
    finally:
        db.close()


@router.delete("/{record_id}", tags=["Medical Records - Cabecera"])
async def delete_medical_record(
    record_id: str,
    current_user: UserSchema = Depends(require_roles("admin"))
):
    """A.5) Eliminar historial completo (solo admin)"""
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        record = db.execute(
            text("SELECT id FROM medical_records WHERE id = :rid"),
            {"rid": record_id}
        ).mappings().first()
        
        if not record:
            raise HTTPException(status_code=404, detail="Medical record not found")
        
        # Eliminar datos relacionados primero (todas las tablas)
        related_tables = [
            "medical_record_signature", "medical_record_clinical_exam",
            "medical_record_exams_cardiovascular", "medical_record_exams_dental",
            "medical_record_exams_digestive_abdominal", "medical_record_exams_genitourinario_mens",
            "medical_record_exams_genitourinario_womens", "medical_record_exams_head_or_neck",
            "medical_record_exams_neurology", "medical_record_exams_oftalmology",
            "medical_record_exams_orl", "medical_record_exams_osteoarticular",
            "medical_record_exams_psychiatric", "medical_record_exams_skin",
            "medical_record_exams_thoracic_respiratory", "medical_record_exposures",
            "medical_record_family_history", "medical_record_habits",
            "medical_record_immunizations", "medical_record_performed_studies",
            "medical_record_personal_history", "medical_record_surgeries",
            "medical_record_symptoms", "medical_record_work_risks",
            "occupational_history_entries"
        ]
        
        for table in related_tables:
            db.execute(text(f"DELETE FROM {table} WHERE record_id = :rid"), {"rid": record_id})
        
        # Eliminar record principal
        db.execute(text("DELETE FROM medical_records WHERE id = :rid"), {"rid": record_id})
        
        db.commit()
        return {"detail": "Medical record deleted successfully", "record_id": record_id}
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Error deleting medical record")
    finally:
        db.close()


# ============================================================================
# B) FIRMA (medical_record_signature table)
# ============================================================================

@router.get("/{record_id}/signature", tags=["Medical Records - Firma"])
async def get_signature(
    record_id: str,
    current_user: UserSchema = Depends(require_active_user)
):
    """B.1) Obtener firma de un historial"""
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        _check_record_access(current_user, record_id, db)
        
        sig = db.execute(
            text("""
                SELECT id, record_id, signed_by_professional_id, signer_role, 
                       signature_image_path, signature_image_mime, signature_date, 
                       licence, created_at, updated_at
                FROM medical_record_signature
                WHERE record_id = :rid
                LIMIT 1
            """),
            {"rid": record_id}
        ).mappings().first()
        
        if not sig:
            return {"detail": "No signature found", "record_id": record_id}
        
        return {
            "id": sig["id"],
            "record_id": sig["record_id"],
            "signed_by_professional_id": sig["signed_by_professional_id"],
            "signer_role": sig["signer_role"],
            "signature_image_path": sig["signature_image_path"],
            "signature_image_mime": sig["signature_image_mime"],
            "signature_date": sig["signature_date"],
            "licence": sig["licence"],
            "created_at": sig["created_at"],
            "updated_at": sig["updated_at"],
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error fetching signature")
    finally:
        db.close()

@router.patch("/{record_id}/signature", tags=["Medical Records - Firma"])
async def update_signature(
    record_id: str,
    signature_image_base64: str = Form(...),
    signature_image_mime: str = Form(...),
    signature_date: str = Form(...),
    licence: str = Form(...),
    current_user: UserSchema = Depends(require_roles("professional", "admin"))
):
    """B.2) Crear/Actualizar firma"""
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        # Validar record existe
        record = db.execute(
            text("SELECT id FROM medical_records WHERE id = :rid"),
            {"rid": record_id}
        ).mappings().first()
        
        if not record:
            raise HTTPException(status_code=404, detail="Medical record not found")
        
        # Obtener professional_id
        if current_user.role == "professional":
            professional_id = _get_professional_id(db, current_user.id)
        elif current_user.role == "admin":
            # Admin puede firmar sin ser professional
            professional_id = None
        else:
            raise HTTPException(status_code=400, detail="Only professionals or admins can sign")
        
        # Borrar firma anterior si existe
        db.execute(
            text("DELETE FROM medical_record_signature WHERE record_id = :rid"),
            {"rid": record_id}
        )
        
        # Crear nueva firma
        signature_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        
        db.execute(text("""
            INSERT INTO medical_record_signature
            (id, record_id, signed_by_professional_id, signer_role, signature_image_path, 
             signature_image_mime, signature_date, licence, created_at, updated_at)
            VALUES 
            (:id, :record_id, :professional_id, :role, :image_path, :mime, :date, :licence, :created, :updated)
        """), {
            "id": signature_id,
            "record_id": record_id,
            "professional_id": professional_id,
            "role": current_user.role,
            "image_path": signature_image_base64,
            "mime": signature_image_mime,
            "date": signature_date,
            "licence": licence,
            "created": now,
            "updated": now,
        })
        
        db.commit()
        
        return {
            "detail": "Signature updated successfully",
            "record_id": record_id,
            "signature_id": signature_id
        }
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Error updating signature")
    finally:
        db.close()

@router.get("/{record_id}/clinical-exam", tags=["Medical Records - Examen Clínico"])
async def get_clinical_exam(
    record_id: str,
    current_user: UserSchema = Depends(require_active_user)
):
    """C.1.1) Obtener examen clínico"""
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        _check_record_access(current_user, record_id, db)
        
        exam = db.execute(
            text("""
                SELECT id, record_id, height_cm, weight_kg, spo2_percent, bmi,
                       blood_pressure_min, blood_pressure_max
                FROM medical_record_clinical_exam
                WHERE record_id = :rid
                LIMIT 1
            """),
            {"rid": record_id}
        ).mappings().first()
        
        if not exam:
            return {"detail": "No clinical exam found", "record_id": record_id}
        
        return {
            "id": exam["id"],
            "record_id": exam["record_id"],
            "height_cm": exam["height_cm"],
            "weight_kg": exam["weight_kg"],
            "spo2_percent": exam["spo2_percent"],
            "bmi": exam["bmi"],
            "blood_pressure_min": exam["blood_pressure_min"],
            "blood_pressure_max": exam["blood_pressure_max"],
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error fetching clinical exam")
    finally:
        db.close()


@router.patch("/{record_id}/clinical-exam", tags=["Medical Records - Examen Clínico"])
async def update_clinical_exam(
    record_id: str,
    height_cm: float = Form(default=None),
    weight_kg: float = Form(default=None),
    spo2_percent: float = Form(default=None),
    bmi: float = Form(default=None),
    blood_pressure_min: str = Form(default=None),
    blood_pressure_max: str = Form(default=None),
    current_user: UserSchema = Depends(require_roles("professional", "admin"))
):
    """C.1.2) Crear/Actualizar examen clínico"""
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        record = db.execute(
            text("SELECT created_by_user_id FROM medical_records WHERE id = :rid"),
            {"rid": record_id}
        ).mappings().first()
        
        if not record:
            raise HTTPException(status_code=404, detail="Medical record not found")
        
        if current_user.role != "admin" and record["created_by_user_id"] != current_user.id:
            raise HTTPException(status_code=403, detail="You can only modify your own records")
        
        # Obtener o crear examen clínico
        exam = db.execute(
            text("SELECT id FROM medical_record_clinical_exam WHERE record_id = :rid"),
            {"rid": record_id}
        ).mappings().first()
        
        if exam:
            # Actualizar existente
            updates = []
            params: dict[str, Any] = {"record_id": record_id}
            
            if height_cm is not None:
                updates.append("height_cm = :height_cm")
                params["height_cm"] = height_cm
            if weight_kg is not None:
                updates.append("weight_kg = :weight_kg")
                params["weight_kg"] = weight_kg
            if spo2_percent is not None:
                updates.append("spo2_percent = :spo2_percent")
                params["spo2_percent"] = spo2_percent
            if bmi is not None:
                updates.append("bmi = :bmi")
                params["bmi"] = bmi
            if blood_pressure_min is not None:
                updates.append("blood_pressure_min = :blood_pressure_min")
                params["blood_pressure_min"] = blood_pressure_min
            if blood_pressure_max is not None:
                updates.append("blood_pressure_max = :blood_pressure_max")
                params["blood_pressure_max"] = blood_pressure_max
            
            if updates:
                db.execute(
                    text(f"UPDATE medical_record_clinical_exam SET {', '.join(updates)} WHERE record_id = :record_id"),
                    params
                )
        else:
            # Crear nuevo
            exam_id = str(uuid.uuid4())
            db.execute(text("""
                INSERT INTO medical_record_clinical_exam
                (id, record_id, height_cm, weight_kg, spo2_percent, bmi, blood_pressure_min, blood_pressure_max)
                VALUES (:id, :record_id, :height_cm, :weight_kg, :spo2_percent, :bmi, :blood_pressure_min, :blood_pressure_max)
            """), {
                "id": exam_id,
                "record_id": record_id,
                "height_cm": height_cm,
                "weight_kg": weight_kg,
                "spo2_percent": spo2_percent,
                "bmi": bmi,
                "blood_pressure_min": blood_pressure_min,
                "blood_pressure_max": blood_pressure_max,
            })
        
        db.commit()
        return {"detail": "Clinical exam updated successfully", "record_id": record_id}
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Error updating clinical exam")
    finally:
        db.close()

@router.get("/{record_id}/exams/skin", tags=["Medical Records - Piel"])
async def get_skin_exam(
    record_id: str,
    current_user: UserSchema = Depends(require_active_user)
):
    """C.2.1) Obtener examen de piel"""
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        _check_record_access(current_user, record_id, db)
        
        exam = db.execute(
            text("""
                SELECT id, record_id, skin_alterations, skin_piercings, skin_tattoos, 
                       skin_scars, skin_observations
                FROM medical_record_exams_skin
                WHERE record_id = :rid
                LIMIT 1
            """),
            {"rid": record_id}
        ).mappings().first()
        
        if not exam:
            return {"detail": "No skin exam found", "record_id": record_id}
        
        return {
            "id": exam["id"],
            "record_id": exam["record_id"],
            "skin_alterations": exam["skin_alterations"],
            "skin_piercings": exam["skin_piercings"],
            "skin_tattoos": exam["skin_tattoos"],
            "skin_scars": exam["skin_scars"],
            "skin_observations": exam["skin_observations"],
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error fetching skin exam")
    finally:
        db.close()


@router.patch("/{record_id}/exams/skin", tags=["Medical Records - Piel"])
async def update_skin_exam(
    record_id: str,
    skin_alterations: int = Form(default=None),
    skin_piercings: int = Form(default=None),
    skin_tattoos: int = Form(default=None),
    skin_scars: int = Form(default=None),
    skin_observations: str = Form(default=None),
    current_user: UserSchema = Depends(require_roles("professional", "admin"))
):
    """C.2.2) Crear/Actualizar examen de piel"""
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        record = db.execute(
            text("SELECT created_by_user_id FROM medical_records WHERE id = :rid"),
            {"rid": record_id}
        ).mappings().first()
        
        if not record:
            raise HTTPException(status_code=404, detail="Medical record not found")
        
        if current_user.role != "admin" and record["created_by_user_id"] != current_user.id:
            raise HTTPException(status_code=403, detail="You can only modify your own records")
        
        exam = db.execute(
            text("SELECT id FROM medical_record_exams_skin WHERE record_id = :rid"),
            {"rid": record_id}
        ).mappings().first()
        
        if exam:
            updates = []
            params: dict[str, Any] = {"record_id": record_id}
            
            if skin_alterations is not None:
                updates.append("skin_alterations = :skin_alterations")
                params["skin_alterations"] = skin_alterations
            if skin_piercings is not None:
                updates.append("skin_piercings = :skin_piercings")
                params["skin_piercings"] = skin_piercings
            if skin_tattoos is not None:
                updates.append("skin_tattoos = :skin_tattoos")
                params["skin_tattoos"] = skin_tattoos
            if skin_scars is not None:
                updates.append("skin_scars = :skin_scars")
                params["skin_scars"] = skin_scars
            if skin_observations is not None:
                updates.append("skin_observations = :skin_observations")
                params["skin_observations"] = skin_observations
            
            if updates:
                db.execute(
                    text(f"UPDATE medical_record_exams_skin SET {', '.join(updates)} WHERE record_id = :record_id"),
                    params
                )
        else:
            exam_id = str(uuid.uuid4())
            db.execute(text("""
                INSERT INTO medical_record_exams_skin
                (id, record_id, skin_alterations, skin_piercings, skin_tattoos, skin_scars, skin_observations)
                VALUES (:id, :record_id, :skin_alterations, :skin_piercings, :skin_tattoos, :skin_scars, :skin_observations)
            """), {
                "id": exam_id,
                "record_id": record_id,
                "skin_alterations": skin_alterations,
                "skin_piercings": skin_piercings,
                "skin_tattoos": skin_tattoos,
                "skin_scars": skin_scars,
                "skin_observations": skin_observations,
            })
        
        db.commit()
        return {"detail": "Skin exam updated successfully", "record_id": record_id}
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Error updating skin exam")
    finally:
        db.close()

@router.get("/{record_id}/exams/oftalmology", tags=["Medical Records - Oftalmología"])
async def get_oftalmology_exam(
    record_id: str,
    current_user: UserSchema = Depends(require_active_user)
):
    """C.3.1) Obtener examen oftalmológico"""
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        _check_record_access(current_user, record_id, db)
        
        exam = db.execute(
            text("""
                SELECT id, record_id, vision_far_od_sc, vision_far_oi_sc, 
                       vision_far_od_cc, vision_far_oi_cc, vision_near_od_sc, 
                       vision_near_oi_sc, vision_near_od_cc, vision_near_oi_cc,
                       color_vision_normal, color_vision_abnormal, ophthalmologic_observations
                FROM medical_record_exams_oftalmology
                WHERE record_id = :rid
                LIMIT 1
            """),
            {"rid": record_id}
        ).mappings().first()
        
        if not exam:
            return {"detail": "No oftalmology exam found", "record_id": record_id}
        
        return {
            "id": exam["id"],
            "record_id": exam["record_id"],
            "vision_far_od_sc": exam["vision_far_od_sc"],
            "vision_far_oi_sc": exam["vision_far_oi_sc"],
            "vision_far_od_cc": exam["vision_far_od_cc"],
            "vision_far_oi_cc": exam["vision_far_oi_cc"],
            "vision_near_od_sc": exam["vision_near_od_sc"],
            "vision_near_oi_sc": exam["vision_near_oi_sc"],
            "vision_near_od_cc": exam["vision_near_od_cc"],
            "vision_near_oi_cc": exam["vision_near_oi_cc"],
            "color_vision_normal": exam["color_vision_normal"],
            "color_vision_abnormal": exam["color_vision_abnormal"],
            "ophthalmologic_observations": exam["ophthalmologic_observations"],
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error fetching oftalmology exam")
    finally:
        db.close()


@router.patch("/{record_id}/exams/oftalmology", tags=["Medical Records - Oftalmología"])
async def update_oftalmology_exam(
    record_id: str,
    vision_far_od_sc: str = Form(default=None),
    vision_far_oi_sc: str = Form(default=None),
    vision_far_od_cc: str = Form(default=None),
    vision_far_oi_cc: str = Form(default=None),
    vision_near_od_sc: str = Form(default=None),
    vision_near_oi_sc: str = Form(default=None),
    vision_near_od_cc: str = Form(default=None),
    vision_near_oi_cc: str = Form(default=None),
    color_vision_normal: int = Form(default=None),
    color_vision_abnormal: int = Form(default=None),
    ophthalmologic_observations: str = Form(default=None),
    current_user: UserSchema = Depends(require_roles("professional", "admin"))
):
    """C.3.2) Crear/Actualizar examen oftalmológico"""
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        record = db.execute(
            text("SELECT created_by_user_id FROM medical_records WHERE id = :rid"),
            {"rid": record_id}
        ).mappings().first()
        
        if not record:
            raise HTTPException(status_code=404, detail="Medical record not found")
        
        if current_user.role != "admin" and record["created_by_user_id"] != current_user.id:
            raise HTTPException(status_code=403, detail="You can only modify your own records")
        
        exam = db.execute(
            text("SELECT id FROM medical_record_exams_oftalmology WHERE record_id = :rid"),
            {"rid": record_id}
        ).mappings().first()
        
        if exam:
            updates = []
            params: dict[str, Any] = {"record_id": record_id}
            
            if vision_far_od_sc is not None:
                updates.append("vision_far_od_sc = :vision_far_od_sc")
                params["vision_far_od_sc"] = vision_far_od_sc
            if vision_far_oi_sc is not None:
                updates.append("vision_far_oi_sc = :vision_far_oi_sc")
                params["vision_far_oi_sc"] = vision_far_oi_sc
            if vision_far_od_cc is not None:
                updates.append("vision_far_od_cc = :vision_far_od_cc")
                params["vision_far_od_cc"] = vision_far_od_cc
            if vision_far_oi_cc is not None:
                updates.append("vision_far_oi_cc = :vision_far_oi_cc")
                params["vision_far_oi_cc"] = vision_far_oi_cc
            if vision_near_od_sc is not None:
                updates.append("vision_near_od_sc = :vision_near_od_sc")
                params["vision_near_od_sc"] = vision_near_od_sc
            if vision_near_oi_sc is not None:
                updates.append("vision_near_oi_sc = :vision_near_oi_sc")
                params["vision_near_oi_sc"] = vision_near_oi_sc
            if vision_near_od_cc is not None:
                updates.append("vision_near_od_cc = :vision_near_od_cc")
                params["vision_near_od_cc"] = vision_near_od_cc
            if vision_near_oi_cc is not None:
                updates.append("vision_near_oi_cc = :vision_near_oi_cc")
                params["vision_near_oi_cc"] = vision_near_oi_cc
            if color_vision_normal is not None:
                updates.append("color_vision_normal = :color_vision_normal")
                params["color_vision_normal"] = color_vision_normal
            if color_vision_abnormal is not None:
                updates.append("color_vision_abnormal = :color_vision_abnormal")
                params["color_vision_abnormal"] = color_vision_abnormal
            if ophthalmologic_observations is not None:
                updates.append("ophthalmologic_observations = :ophthalmologic_observations")
                params["ophthalmologic_observations"] = ophthalmologic_observations
            
            if updates:
                db.execute(
                    text(f"UPDATE medical_record_exams_oftalmology SET {', '.join(updates)} WHERE record_id = :record_id"),
                    params
                )
        else:
            exam_id = str(uuid.uuid4())
            db.execute(text("""
                INSERT INTO medical_record_exams_oftalmology
                (id, record_id, vision_far_od_sc, vision_far_oi_sc, vision_far_od_cc, vision_far_oi_cc,
                 vision_near_od_sc, vision_near_oi_sc, vision_near_od_cc, vision_near_oi_cc,
                 color_vision_normal, color_vision_abnormal, ophthalmologic_observations)
                VALUES (:id, :record_id, :vision_far_od_sc, :vision_far_oi_sc, :vision_far_od_cc, :vision_far_oi_cc,
                 :vision_near_od_sc, :vision_near_oi_sc, :vision_near_od_cc, :vision_near_oi_cc,
                 :color_vision_normal, :color_vision_abnormal, :ophthalmologic_observations)
            """), {
                "id": exam_id,
                "record_id": record_id,
                "vision_far_od_sc": vision_far_od_sc,
                "vision_far_oi_sc": vision_far_oi_sc,
                "vision_far_od_cc": vision_far_od_cc,
                "vision_far_oi_cc": vision_far_oi_cc,
                "vision_near_od_sc": vision_near_od_sc,
                "vision_near_oi_sc": vision_near_oi_sc,
                "vision_near_od_cc": vision_near_od_cc,
                "vision_near_oi_cc": vision_near_oi_cc,
                "color_vision_normal": color_vision_normal,
                "color_vision_abnormal": color_vision_abnormal,
                "ophthalmologic_observations": ophthalmologic_observations,
            })
        
        db.commit()
        return {"detail": "Oftalmology exam updated successfully", "record_id": record_id}
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Error updating oftalmology exam")
    finally:
        db.close()

@router.get("/{record_id}/exams/dental", tags=["Medical Records - Dental"])
async def get_dental_exam(
    record_id: str,
    current_user: UserSchema = Depends(require_active_user)
):
    """C.4.1) Obtener examen dental"""
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        _check_record_access(current_user, record_id, db)
        
        exam = db.execute(
            text("""
                SELECT id, record_id, dental_prosthesis, dental_caries, 
                       dental_gum_alterations, dental_partial_dentition, dental_observations
                FROM medical_record_exams_dental
                WHERE record_id = :rid
                LIMIT 1
            """),
            {"rid": record_id}
        ).mappings().first()
        
        if not exam:
            return {"detail": "No dental exam found", "record_id": record_id}
        
        return {
            "id": exam["id"],
            "record_id": exam["record_id"],
            "dental_prosthesis": exam["dental_prosthesis"],
            "dental_caries": exam["dental_caries"],
            "dental_gum_alterations": exam["dental_gum_alterations"],
            "dental_partial_dentition": exam["dental_partial_dentition"],
            "dental_observations": exam["dental_observations"],
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error fetching dental exam")
    finally:
        db.close()


@router.patch("/{record_id}/exams/dental", tags=["Medical Records - Dental"])
async def update_dental_exam(
    record_id: str,
    dental_prosthesis: int = Form(default=None),
    dental_caries: int = Form(default=None),
    dental_gum_alterations: int = Form(default=None),
    dental_partial_dentition: int = Form(default=None),
    dental_observations: str = Form(default=None),
    current_user: UserSchema = Depends(require_roles("professional", "admin"))
):
    """C.4.2) Crear/Actualizar examen dental"""
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        record = db.execute(
            text("SELECT created_by_user_id FROM medical_records WHERE id = :rid"),
            {"rid": record_id}
        ).mappings().first()
        
        if not record:
            raise HTTPException(status_code=404, detail="Medical record not found")
        
        if current_user.role != "admin" and record["created_by_user_id"] != current_user.id:
            raise HTTPException(status_code=403, detail="You can only modify your own records")
        
        exam = db.execute(
            text("SELECT id FROM medical_record_exams_dental WHERE record_id = :rid"),
            {"rid": record_id}
        ).mappings().first()
        
        if exam:
            updates = []
            params: dict[str, Any] = {"record_id": record_id}
            
            if dental_prosthesis is not None:
                updates.append("dental_prosthesis = :dental_prosthesis")
                params["dental_prosthesis"] = dental_prosthesis
            if dental_caries is not None:
                updates.append("dental_caries = :dental_caries")
                params["dental_caries"] = dental_caries
            if dental_gum_alterations is not None:
                updates.append("dental_gum_alterations = :dental_gum_alterations")
                params["dental_gum_alterations"] = dental_gum_alterations
            if dental_partial_dentition is not None:
                updates.append("dental_partial_dentition = :dental_partial_dentition")
                params["dental_partial_dentition"] = dental_partial_dentition
            if dental_observations is not None:
                updates.append("dental_observations = :dental_observations")
                params["dental_observations"] = dental_observations
            
            if updates:
                db.execute(
                    text(f"UPDATE medical_record_exams_dental SET {', '.join(updates)} WHERE record_id = :record_id"),
                    params
                )
        else:
            exam_id = str(uuid.uuid4())
            db.execute(text("""
                INSERT INTO medical_record_exams_dental
                (id, record_id, dental_prosthesis, dental_caries, dental_gum_alterations, dental_partial_dentition, dental_observations)
                VALUES (:id, :record_id, :dental_prosthesis, :dental_caries, :dental_gum_alterations, :dental_partial_dentition, :dental_observations)
            """), {
                "id": exam_id,
                "record_id": record_id,
                "dental_prosthesis": dental_prosthesis,
                "dental_caries": dental_caries,
                "dental_gum_alterations": dental_gum_alterations,
                "dental_partial_dentition": dental_partial_dentition,
                "dental_observations": dental_observations,
            })
        
        db.commit()
        return {"detail": "Dental exam updated successfully", "record_id": record_id}
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Error updating dental exam")
    finally:
        db.close()

@router.get("/{record_id}/exams/orl", tags=["Medical Records - ORL"])
async def get_orl_exam(
    record_id: str,
    current_user: UserSchema = Depends(require_active_user)
):
    """C.5.1) Obtener examen ORL"""
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        _check_record_access(current_user, record_id, db)
        
        exam = db.execute(
            text("""
                SELECT id, record_id, pharynx_patology, tonsils_patology, 
                       voice_alterations, rinitis, audition_disorders, 
                       lymphadenopathy, orl_observations
                FROM medical_record_exams_orl
                WHERE record_id = :rid
                LIMIT 1
            """),
            {"rid": record_id}
        ).mappings().first()
        
        if not exam:
            return {"detail": "No ORL exam found", "record_id": record_id}
        
        return {
            "id": exam["id"],
            "record_id": exam["record_id"],
            "pharynx_patology": exam["pharynx_patology"],
            "tonsils_patology": exam["tonsils_patology"],
            "voice_alterations": exam["voice_alterations"],
            "rinitis": exam["rinitis"],
            "audition_disorders": exam["audition_disorders"],
            "lymphadenopathy": exam["lymphadenopathy"],
            "orl_observations": exam["orl_observations"],
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error fetching ORL exam")
    finally:
        db.close()


@router.patch("/{record_id}/exams/orl", tags=["Medical Records - ORL"])
async def update_orl_exam(
    record_id: str,
    pharynx_patology: int = Form(default=None),
    tonsils_patology: int = Form(default=None),
    voice_alterations: int = Form(default=None),
    rinitis: int = Form(default=None),
    audition_disorders: int = Form(default=None),
    lymphadenopathy: int = Form(default=None),
    orl_observations: str = Form(default=None),
    current_user: UserSchema = Depends(require_roles("professional", "admin"))
):
    """C.5.2) Crear/Actualizar examen ORL"""
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        record = db.execute(
            text("SELECT created_by_user_id FROM medical_records WHERE id = :rid"),
            {"rid": record_id}
        ).mappings().first()
        
        if not record:
            raise HTTPException(status_code=404, detail="Medical record not found")
        
        if current_user.role != "admin" and record["created_by_user_id"] != current_user.id:
            raise HTTPException(status_code=403, detail="You can only modify your own records")
        
        exam = db.execute(
            text("SELECT id FROM medical_record_exams_orl WHERE record_id = :rid"),
            {"rid": record_id}
        ).mappings().first()
        
        if exam:
            updates = []
            params: dict[str, Any] = {"record_id": record_id}
            
            if pharynx_patology is not None:
                updates.append("pharynx_patology = :pharynx_patology")
                params["pharynx_patology"] = pharynx_patology
            if tonsils_patology is not None:
                updates.append("tonsils_patology = :tonsils_patology")
                params["tonsils_patology"] = tonsils_patology
            if voice_alterations is not None:
                updates.append("voice_alterations = :voice_alterations")
                params["voice_alterations"] = voice_alterations
            if rinitis is not None:
                updates.append("rinitis = :rinitis")
                params["rinitis"] = rinitis
            if audition_disorders is not None:
                updates.append("audition_disorders = :audition_disorders")
                params["audition_disorders"] = audition_disorders
            if lymphadenopathy is not None:
                updates.append("lymphadenopathy = :lymphadenopathy")
                params["lymphadenopathy"] = lymphadenopathy
            if orl_observations is not None:
                updates.append("orl_observations = :orl_observations")
                params["orl_observations"] = orl_observations
            
            if updates:
                db.execute(
                    text(f"UPDATE medical_record_exams_orl SET {', '.join(updates)} WHERE record_id = :record_id"),
                    params
                )
        else:
            exam_id = str(uuid.uuid4())
            db.execute(text("""
                INSERT INTO medical_record_exams_orl
                (id, record_id, pharynx_patology, tonsils_patology, voice_alterations, 
                 rinitis, audition_disorders, lymphadenopathy, orl_observations)
                VALUES (:id, :record_id, :pharynx_patology, :tonsils_patology, :voice_alterations,
                 :rinitis, :audition_disorders, :lymphadenopathy, :orl_observations)
            """), {
                "id": exam_id,
                "record_id": record_id,
                "pharynx_patology": pharynx_patology,
                "tonsils_patology": tonsils_patology,
                "voice_alterations": voice_alterations,
                "rinitis": rinitis,
                "audition_disorders": audition_disorders,
                "lymphadenopathy": lymphadenopathy,
                "orl_observations": orl_observations,
            })
        
        db.commit()
        return {"detail": "ORL exam updated successfully", "record_id": record_id}
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Error updating ORL exam")
    finally:
        db.close()

@router.get("/{record_id}/exams/head-or-neck", tags=["Medical Records - Cabeza/Cuello"])
async def get_head_neck_exam(
    record_id: str,
    current_user: UserSchema = Depends(require_active_user)
):
    """C.6.1) Obtener examen cabeza o cuello"""
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        _check_record_access(current_user, record_id, db)
        
        exam = db.execute(
            text("""
                SELECT id, record_id, disorder_movility, disorder_carotid_pulses, 
                       thyroid_tumors, head_lymphadenopathy, head_neck_observations
                FROM medical_record_exams_head_or_neck
                WHERE record_id = :rid
                LIMIT 1
            """),
            {"rid": record_id}
        ).mappings().first()
        
        if not exam:
            return {"detail": "No head/neck exam found", "record_id": record_id}
        
        return {
            "id": exam["id"],
            "record_id": exam["record_id"],
            "disorder_movility": exam["disorder_movility"],
            "disorder_carotid_pulses": exam["disorder_carotid_pulses"],
            "thyroid_tumors": exam["thyroid_tumors"],
            "head_lymphadenopathy": exam["head_lymphadenopathy"],
            "head_neck_observations": exam["head_neck_observations"],
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error fetching head/neck exam")
    finally:
        db.close()


@router.patch("/{record_id}/exams/head-or-neck", tags=["Medical Records - Cabeza/Cuello"])
async def update_head_neck_exam(
    record_id: str,
    disorder_movility: int = Form(default=None),
    disorder_carotid_pulses: int = Form(default=None),
    thyroid_tumors: int = Form(default=None),
    head_lymphadenopathy: int = Form(default=None),
    head_neck_observations: str = Form(default=None),
    current_user: UserSchema = Depends(require_roles("professional", "admin"))
):
    """C.6.2) Crear/Actualizar examen cabeza o cuello"""
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        record = db.execute(
            text("SELECT created_by_user_id FROM medical_records WHERE id = :rid"),
            {"rid": record_id}
        ).mappings().first()
        
        if not record:
            raise HTTPException(status_code=404, detail="Medical record not found")
        
        if current_user.role != "admin" and record["created_by_user_id"] != current_user.id:
            raise HTTPException(status_code=403, detail="You can only modify your own records")
        
        exam = db.execute(
            text("SELECT id FROM medical_record_exams_head_or_neck WHERE record_id = :rid"),
            {"rid": record_id}
        ).mappings().first()
        
        if exam:
            updates = []
            params: dict[str, Any] = {"record_id": record_id}
            
            if disorder_movility is not None:
                updates.append("disorder_movility = :disorder_movility")
                params["disorder_movility"] = disorder_movility
            if disorder_carotid_pulses is not None:
                updates.append("disorder_carotid_pulses = :disorder_carotid_pulses")
                params["disorder_carotid_pulses"] = disorder_carotid_pulses
            if thyroid_tumors is not None:
                updates.append("thyroid_tumors = :thyroid_tumors")
                params["thyroid_tumors"] = thyroid_tumors
            if head_lymphadenopathy is not None:
                updates.append("head_lymphadenopathy = :head_lymphadenopathy")
                params["head_lymphadenopathy"] = head_lymphadenopathy
            if head_neck_observations is not None:
                updates.append("head_neck_observations = :head_neck_observations")
                params["head_neck_observations"] = head_neck_observations
            
            if updates:
                db.execute(
                    text(f"UPDATE medical_record_exams_head_or_neck SET {', '.join(updates)} WHERE record_id = :record_id"),
                    params
                )
        else:
            exam_id = str(uuid.uuid4())
            db.execute(text("""
                INSERT INTO medical_record_exams_head_or_neck
                (id, record_id, disorder_movility, disorder_carotid_pulses, thyroid_tumors, 
                 head_lymphadenopathy, head_neck_observations)
                VALUES (:id, :record_id, :disorder_movility, :disorder_carotid_pulses, :thyroid_tumors,
                 :head_lymphadenopathy, :head_neck_observations)
            """), {
                "id": exam_id,
                "record_id": record_id,
                "disorder_movility": disorder_movility,
                "disorder_carotid_pulses": disorder_carotid_pulses,
                "thyroid_tumors": thyroid_tumors,
                "head_lymphadenopathy": head_lymphadenopathy,
                "head_neck_observations": head_neck_observations,
            })
        
        db.commit()
        return {"detail": "Head/neck exam updated successfully", "record_id": record_id}
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Error updating head/neck exam")
    finally:
        db.close()

@router.get("/{record_id}/exams/cardiovascular", tags=["Medical Records - Cardiovascular"])
async def get_cardiovascular_exam(
    record_id: str,
    current_user: UserSchema = Depends(require_active_user)
):
    """C.7.1) Obtener examen cardiovascular"""
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        _check_record_access(current_user, record_id, db)
        
        exam = db.execute(
            text("""
                SELECT id, record_id, cardio_freq, arterial_tension, irregular_hearth_rate,
                       disorder_hearth_sounds, extrasistoles, whispers, absent_peripheral_pulses,
                       varices, cardiovascular_observations
                FROM medical_record_exams_cardiovascular
                WHERE record_id = :rid
                LIMIT 1
            """),
            {"rid": record_id}
        ).mappings().first()
        
        if not exam:
            return {"detail": "No cardiovascular exam found", "record_id": record_id}
        
        return {
            "id": exam["id"],
            "record_id": exam["record_id"],
            "cardio_freq": exam["cardio_freq"],
            "arterial_tension": exam["arterial_tension"],
            "irregular_hearth_rate": exam["irregular_hearth_rate"],
            "disorder_hearth_sounds": exam["disorder_hearth_sounds"],
            "extrasistoles": exam["extrasistoles"],
            "whispers": exam["whispers"],
            "absent_peripheral_pulses": exam["absent_peripheral_pulses"],
            "varices": exam["varices"],
            "cardiovascular_observations": exam["cardiovascular_observations"],
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error fetching cardiovascular exam")
    finally:
        db.close()


@router.patch("/{record_id}/exams/cardiovascular", tags=["Medical Records - Cardiovascular"])
async def update_cardiovascular_exam(
    record_id: str,
    cardio_freq: int = Form(default=None),
    arterial_tension: float = Form(default=None),
    irregular_hearth_rate: int = Form(default=None),
    disorder_hearth_sounds: int = Form(default=None),
    extrasistoles: int = Form(default=None),
    whispers: int = Form(default=None),
    absent_peripheral_pulses: int = Form(default=None),
    varices: int = Form(default=None),
    cardiovascular_observations: str = Form(default=None),
    current_user: UserSchema = Depends(require_roles("professional", "admin"))
):
    """C.7.2) Crear/Actualizar examen cardiovascular"""
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        record = db.execute(
            text("SELECT created_by_user_id FROM medical_records WHERE id = :rid"),
            {"rid": record_id}
        ).mappings().first()
        
        if not record:
            raise HTTPException(status_code=404, detail="Medical record not found")
        
        if current_user.role != "admin" and record["created_by_user_id"] != current_user.id:
            raise HTTPException(status_code=403, detail="You can only modify your own records")
        
        exam = db.execute(
            text("SELECT id FROM medical_record_exams_cardiovascular WHERE record_id = :rid"),
            {"rid": record_id}
        ).mappings().first()
        
        if exam:
            updates = []
            params: dict[str, Any] = {"record_id": record_id}
            
            if cardio_freq is not None:
                updates.append("cardio_freq = :cardio_freq")
                params["cardio_freq"] = cardio_freq
            if arterial_tension is not None:
                updates.append("arterial_tension = :arterial_tension")
                params["arterial_tension"] = arterial_tension
            if irregular_hearth_rate is not None:
                updates.append("irregular_hearth_rate = :irregular_hearth_rate")
                params["irregular_hearth_rate"] = irregular_hearth_rate
            if disorder_hearth_sounds is not None:
                updates.append("disorder_hearth_sounds = :disorder_hearth_sounds")
                params["disorder_hearth_sounds"] = disorder_hearth_sounds
            if extrasistoles is not None:
                updates.append("extrasistoles = :extrasistoles")
                params["extrasistoles"] = extrasistoles
            if whispers is not None:
                updates.append("whispers = :whispers")
                params["whispers"] = whispers
            if absent_peripheral_pulses is not None:
                updates.append("absent_peripheral_pulses = :absent_peripheral_pulses")
                params["absent_peripheral_pulses"] = absent_peripheral_pulses
            if varices is not None:
                updates.append("varices = :varices")
                params["varices"] = varices
            if cardiovascular_observations is not None:
                updates.append("cardiovascular_observations = :cardiovascular_observations")
                params["cardiovascular_observations"] = cardiovascular_observations
            
            if updates:
                db.execute(
                    text(f"UPDATE medical_record_exams_cardiovascular SET {', '.join(updates)} WHERE record_id = :record_id"),
                    params
                )
        else:
            exam_id = str(uuid.uuid4())
            db.execute(text("""
                INSERT INTO medical_record_exams_cardiovascular
                (id, record_id, cardio_freq, arterial_tension, irregular_hearth_rate, disorder_hearth_sounds,
                 extrasistoles, whispers, absent_peripheral_pulses, varices, cardiovascular_observations)
                VALUES (:id, :record_id, :cardio_freq, :arterial_tension, :irregular_hearth_rate, :disorder_hearth_sounds,
                 :extrasistoles, :whispers, :absent_peripheral_pulses, :varices, :cardiovascular_observations)
            """), {
                "id": exam_id,
                "record_id": record_id,
                "cardio_freq": cardio_freq,
                "arterial_tension": arterial_tension,
                "irregular_hearth_rate": irregular_hearth_rate,
                "disorder_hearth_sounds": disorder_hearth_sounds,
                "extrasistoles": extrasistoles,
                "whispers": whispers,
                "absent_peripheral_pulses": absent_peripheral_pulses,
                "varices": varices,
                "cardiovascular_observations": cardiovascular_observations,
            })
        
        db.commit()
        return {"detail": "Cardiovascular exam updated successfully", "record_id": record_id}
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Error updating cardiovascular exam")
    finally:
        db.close()

@router.get("/{record_id}/exams/thoracic-respiratory", tags=["Medical Records - Torácico"])
async def get_thoracic_respiratory_exam(
    record_id: str,
    current_user: UserSchema = Depends(require_active_user)
):
    """C.8.1) Obtener examen torácico/respiratorio"""
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        _check_record_access(current_user, record_id, db)
        
        exam = db.execute(
            text("""
                SELECT id, record_id, respiratory_freq, thoracic_disorders, rales,
                       roncus_sibilancias, vesicular_murmus_disorder, respiratory_lymphadenopathy,
                       sharp_process_in_course, respiratory_observations
                FROM medical_record_exams_thoracic_respiratory
                WHERE record_id = :rid
                LIMIT 1
            """),
            {"rid": record_id}
        ).mappings().first()
        
        if not exam:
            return {"detail": "No thoracic/respiratory exam found", "record_id": record_id}
        
        return {
            "id": exam["id"],
            "record_id": exam["record_id"],
            "respiratory_freq": exam["respiratory_freq"],
            "thoracic_disorders": exam["thoracic_disorders"],
            "rales": exam["rales"],
            "roncus_sibilancias": exam["roncus_sibilancias"],
            "vesicular_murmus_disorder": exam["vesicular_murmus_disorder"],
            "respiratory_lymphadenopathy": exam["respiratory_lymphadenopathy"],
            "sharp_process_in_course": exam["sharp_process_in_course"],
            "respiratory_observations": exam["respiratory_observations"],
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error fetching thoracic/respiratory exam")
    finally:
        db.close()

@router.patch("/{record_id}/exams/thoracic-respiratory", tags=["Medical Records - Torácico"])
async def update_thoracic_respiratory_exam(
    record_id: str,
    respiratory_freq: int = Form(default=None),
    thoracic_disorders: int = Form(default=None),
    rales: int = Form(default=None),
    roncus_sibilancias: int = Form(default=None),
    vesicular_murmus_disorder: int = Form(default=None),
    respiratory_lymphadenopathy: int = Form(default=None),
    sharp_process_in_course: int = Form(default=None),
    respiratory_observations: str = Form(default=None),
    current_user: UserSchema = Depends(require_roles("professional", "admin"))
):
    """C.8.2) Crear/Actualizar examen torácico/respiratorio"""
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        record = db.execute(
            text("SELECT created_by_user_id FROM medical_records WHERE id = :rid"),
            {"rid": record_id}
        ).mappings().first()
        
        if not record:
            raise HTTPException(status_code=404, detail="Medical record not found")
        
        if current_user.role != "admin" and record["created_by_user_id"] != current_user.id:
            raise HTTPException(status_code=403, detail="You can only modify your own records")
        
        exam = db.execute(
            text("SELECT id FROM medical_record_exams_thoracic_respiratory WHERE record_id = :rid"),
            {"rid": record_id}
        ).mappings().first()
        
        if exam:
            updates = []
            params: dict[str, Any] = {"record_id": record_id}
            
            if respiratory_freq is not None:
                updates.append("respiratory_freq = :respiratory_freq")
                params["respiratory_freq"] = respiratory_freq
            if thoracic_disorders is not None:
                updates.append("thoracic_disorders = :thoracic_disorders")
                params["thoracic_disorders"] = thoracic_disorders
            if rales is not None:
                updates.append("rales = :rales")
                params["rales"] = rales
            if roncus_sibilancias is not None:
                updates.append("roncus_sibilancias = :roncus_sibilancias")
                params["roncus_sibilancias"] = roncus_sibilancias
            if vesicular_murmus_disorder is not None:
                updates.append("vesicular_murmus_disorder = :vesicular_murmus_disorder")
                params["vesicular_murmus_disorder"] = vesicular_murmus_disorder
            if respiratory_lymphadenopathy is not None:
                updates.append("respiratory_lymphadenopathy = :respiratory_lymphadenopathy")
                params["respiratory_lymphadenopathy"] = respiratory_lymphadenopathy
            if sharp_process_in_course is not None:
                updates.append("sharp_process_in_course = :sharp_process_in_course")
                params["sharp_process_in_course"] = sharp_process_in_course
            if respiratory_observations is not None:
                updates.append("respiratory_observations = :respiratory_observations")
                params["respiratory_observations"] = respiratory_observations
            
            if updates:
                db.execute(
                    text(f"UPDATE medical_record_exams_thoracic_respiratory SET {', '.join(updates)} WHERE record_id = :record_id"),
                    params
                )
        else:
            exam_id = str(uuid.uuid4())
            db.execute(text("""
                INSERT INTO medical_record_exams_thoracic_respiratory
                (id, record_id, respiratory_freq, thoracic_disorders, rales, roncus_sibilancias,
                 vesicular_murmus_disorder, respiratory_lymphadenopathy, sharp_process_in_course, respiratory_observations)
                VALUES (:id, :record_id, :respiratory_freq, :thoracic_disorders, :rales, :roncus_sibilancias,
                 :vesicular_murmus_disorder, :respiratory_lymphadenopathy, :sharp_process_in_course, :respiratory_observations)
            """), {
                "id": exam_id,
                "record_id": record_id,
                "respiratory_freq": respiratory_freq,
                "thoracic_disorders": thoracic_disorders,
                "rales": rales,
                "roncus_sibilancias": roncus_sibilancias,
                "vesicular_murmus_disorder": vesicular_murmus_disorder,
                "respiratory_lymphadenopathy": respiratory_lymphadenopathy,
                "sharp_process_in_course": sharp_process_in_course,
                "respiratory_observations": respiratory_observations,
            })
        
        db.commit()
        return {"detail": "Thoracic/respiratory exam updated successfully", "record_id": record_id}
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Error updating thoracic/respiratory exam")
    finally:
        db.close()

@router.get("/{record_id}/exams/digestive-abdominal", tags=["Medical Records - Digestivo"])
async def get_digestive_abdominal_exam(
    record_id: str,
    current_user: UserSchema = Depends(require_active_user)
):
    """C.9.1) Obtener examen digestivo/abdominal"""
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        _check_record_access(current_user, record_id, db)
        
        exam = db.execute(
            text("""
                SELECT id, record_id, surgical_scars, hemorrhoids, abdominal_pains,
                       hepatomegalia, esplenomegalia, digestive_lymphadenopathy, 
                       hernias_eventraciones, digestive_observations
                FROM medical_record_exams_digestive_abdominal
                WHERE record_id = :rid
                LIMIT 1
            """),
            {"rid": record_id}
        ).mappings().first()
        
        if not exam:
            return {"detail": "No digestive/abdominal exam found", "record_id": record_id}
        
        return {
            "id": exam["id"],
            "record_id": exam["record_id"],
            "surgical_scars": exam["surgical_scars"],
            "hemorrhoids": exam["hemorrhoids"],
            "abdominal_pains": exam["abdominal_pains"],
            "hepatomegalia": exam["hepatomegalia"],
            "esplenomegalia": exam["esplenomegalia"],
            "digestive_lymphadenopathy": exam["digestive_lymphadenopathy"],
            "hernias_eventraciones": exam["hernias_eventraciones"],
            "digestive_observations": exam["digestive_observations"],
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error fetching digestive/abdominal exam")
    finally:
        db.close()

@router.patch("/{record_id}/exams/digestive-abdominal", tags=["Medical Records - Digestivo"])
async def update_digestive_abdominal_exam(
    record_id: str,
    surgical_scars: int = Form(default=None),
    hemorrhoids: int = Form(default=None),
    abdominal_pains: int = Form(default=None),
    hepatomegalia: int = Form(default=None),
    esplenomegalia: int = Form(default=None),
    digestive_lymphadenopathy: int = Form(default=None),
    hernias_eventraciones: int = Form(default=None),
    digestive_observations: str = Form(default=None),
    current_user: UserSchema = Depends(require_roles("professional", "admin"))
):
    """C.9.2) Crear/Actualizar examen digestivo/abdominal"""
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        record = db.execute(
            text("SELECT created_by_user_id FROM medical_records WHERE id = :rid"),
            {"rid": record_id}
        ).mappings().first()
        
        if not record:
            raise HTTPException(status_code=404, detail="Medical record not found")
        
        if current_user.role != "admin" and record["created_by_user_id"] != current_user.id:
            raise HTTPException(status_code=403, detail="You can only modify your own records")
        
        exam = db.execute(
            text("SELECT id FROM medical_record_exams_digestive_abdominal WHERE record_id = :rid"),
            {"rid": record_id}
        ).mappings().first()
        
        if exam:
            updates = []
            params: dict[str, Any] = {"record_id": record_id}
            
            if surgical_scars is not None:
                updates.append("surgical_scars = :surgical_scars")
                params["surgical_scars"] = surgical_scars
            if hemorrhoids is not None:
                updates.append("hemorrhoids = :hemorrhoids")
                params["hemorrhoids"] = hemorrhoids
            if abdominal_pains is not None:
                updates.append("abdominal_pains = :abdominal_pains")
                params["abdominal_pains"] = abdominal_pains
            if hepatomegalia is not None:
                updates.append("hepatomegalia = :hepatomegalia")
                params["hepatomegalia"] = hepatomegalia
            if esplenomegalia is not None:
                updates.append("esplenomegalia = :esplenomegalia")
                params["esplenomegalia"] = esplenomegalia
            if digestive_lymphadenopathy is not None:
                updates.append("digestive_lymphadenopathy = :digestive_lymphadenopathy")
                params["digestive_lymphadenopathy"] = digestive_lymphadenopathy
            if hernias_eventraciones is not None:
                updates.append("hernias_eventraciones = :hernias_eventraciones")
                params["hernias_eventraciones"] = hernias_eventraciones
            if digestive_observations is not None:
                updates.append("digestive_observations = :digestive_observations")
                params["digestive_observations"] = digestive_observations
            
            if updates:
                db.execute(
                    text(f"UPDATE medical_record_exams_digestive_abdominal SET {', '.join(updates)} WHERE record_id = :record_id"),
                    params
                )
        else:
            exam_id = str(uuid.uuid4())
            db.execute(text("""
                INSERT INTO medical_record_exams_digestive_abdominal
                (id, record_id, surgical_scars, hemorrhoids, abdominal_pains, hepatomegalia,
                 esplenomegalia, digestive_lymphadenopathy, hernias_eventraciones, digestive_observations)
                VALUES (:id, :record_id, :surgical_scars, :hemorrhoids, :abdominal_pains, :hepatomegalia,
                 :esplenomegalia, :digestive_lymphadenopathy, :hernias_eventraciones, :digestive_observations)
            """), {
                "id": exam_id,
                "record_id": record_id,
                "surgical_scars": surgical_scars,
                "hemorrhoids": hemorrhoids,
                "abdominal_pains": abdominal_pains,
                "hepatomegalia": hepatomegalia,
                "esplenomegalia": esplenomegalia,
                "digestive_lymphadenopathy": digestive_lymphadenopathy,
                "hernias_eventraciones": hernias_eventraciones,
                "digestive_observations": digestive_observations,
            })
        
        db.commit()
        return {"detail": "Digestive/abdominal exam updated successfully", "record_id": record_id}
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Error updating digestive/abdominal exam")
    finally:
        db.close()

@router.get("/{record_id}/exams/genitourinary/women", tags=["Medical Records - Genitourinario Mujeres"])
async def get_genitourinary_women_exam(
    record_id: str,
    current_user: UserSchema = Depends(require_active_user)
):
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        _check_record_access(current_user, record_id, db)
        
        exam = db.execute(
            text("""
                SELECT id, record_id, disorder_mammary, disorder_gynecology, fum,
                       menstrual_pains, disorder_flows, anticonceptivos, normal_childbirth,
                       abortos, cesarea, genital_woman_observations
                FROM medical_record_exams_genitourinario_womens
                WHERE record_id = :rid
                LIMIT 1
            """),
            {"rid": record_id}
        ).mappings().first()
        
        if not exam:
            return {"detail": "No genitourinary women exam found", "record_id": record_id}
        
        return {
            "id": exam["id"],
            "record_id": exam["record_id"],
            "disorder_mammary": exam["disorder_mammary"],
            "disorder_gynecology": exam["disorder_gynecology"],
            "fum": exam["fum"],
            "menstrual_pains": exam["menstrual_pains"],
            "disorder_flows": exam["disorder_flows"],
            "anticonceptivos": exam["anticonceptivos"],
            "normal_childbirth": exam["normal_childbirth"],
            "abortos": exam["abortos"],
            "cesarea": exam["cesarea"],
            "genital_woman_observations": exam["genital_woman_observations"],
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error fetching genitourinary women exam")
    finally:
        db.close()


@router.patch("/{record_id}/exams/genitourinary/women", tags=["Medical Records - Genitourinario Mujeres"])
async def update_genitourinary_women_exam(
    record_id: str,
    disorder_mammary: int = Form(default=None),
    disorder_gynecology: int = Form(default=None),
    fum: int = Form(default=None),
    menstrual_pains: int = Form(default=None),
    disorder_flows: int = Form(default=None),
    anticonceptivos: int = Form(default=None),
    normal_childbirth: int = Form(default=None),
    abortos: int = Form(default=None),
    cesarea: int = Form(default=None),
    genital_woman_observations: str = Form(default=None),
    current_user: UserSchema = Depends(require_roles("professional", "admin"))
):
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        record = db.execute(
            text("SELECT created_by_user_id FROM medical_records WHERE id = :rid"),
            {"rid": record_id}
        ).mappings().first()
        
        if not record:
            raise HTTPException(status_code=404, detail="Medical record not found")
        
        if current_user.role != "admin" and record["created_by_user_id"] != current_user.id:
            raise HTTPException(status_code=403, detail="You can only modify your own records")
        
        exam = db.execute(
            text("SELECT id FROM medical_record_exams_genitourinario_womens WHERE record_id = :rid"),
            {"rid": record_id}
        ).mappings().first()
        
        if exam:
            updates = []
            params: dict[str, Any] = {"record_id": record_id}
            
            if disorder_mammary is not None:
                updates.append("disorder_mammary = :disorder_mammary")
                params["disorder_mammary"] = disorder_mammary
            if disorder_gynecology is not None:
                updates.append("disorder_gynecology = :disorder_gynecology")
                params["disorder_gynecology"] = disorder_gynecology
            if fum is not None:
                updates.append("fum = :fum")
                params["fum"] = fum
            if menstrual_pains is not None:
                updates.append("menstrual_pains = :menstrual_pains")
                params["menstrual_pains"] = menstrual_pains
            if disorder_flows is not None:
                updates.append("disorder_flows = :disorder_flows")
                params["disorder_flows"] = disorder_flows
            if anticonceptivos is not None:
                updates.append("anticonceptivos = :anticonceptivos")
                params["anticonceptivos"] = anticonceptivos
            if normal_childbirth is not None:
                updates.append("normal_childbirth = :normal_childbirth")
                params["normal_childbirth"] = normal_childbirth
            if abortos is not None:
                updates.append("abortos = :abortos")
                params["abortos"] = abortos
            if cesarea is not None:
                updates.append("cesarea = :cesarea")
                params["cesarea"] = cesarea
            if genital_woman_observations is not None:
                updates.append("genital_woman_observations = :genital_woman_observations")
                params["genital_woman_observations"] = genital_woman_observations
            
            if updates:
                db.execute(
                    text(f"UPDATE medical_record_exams_genitourinario_womens SET {', '.join(updates)} WHERE record_id = :record_id"),
                    params
                )
        else:
            exam_id = str(uuid.uuid4())
            db.execute(text("""
                INSERT INTO medical_record_exams_genitourinario_womens
                (id, record_id, disorder_mammary, disorder_gynecology, fum, menstrual_pains,
                 disorder_flows, anticonceptivos, normal_childbirth, abortos, cesarea, genital_woman_observations)
                VALUES (:id, :record_id, :disorder_mammary, :disorder_gynecology, :fum, :menstrual_pains,
                 :disorder_flows, :anticonceptivos, :normal_childbirth, :abortos, :cesarea, :genital_woman_observations)
            """), {
                "id": exam_id,
                "record_id": record_id,
                "disorder_mammary": disorder_mammary,
                "disorder_gynecology": disorder_gynecology,
                "fum": fum,
                "menstrual_pains": menstrual_pains,
                "disorder_flows": disorder_flows,
                "anticonceptivos": anticonceptivos,
                "normal_childbirth": normal_childbirth,
                "abortos": abortos,
                "cesarea": cesarea,
                "genital_woman_observations": genital_woman_observations,
            })
        
        db.commit()
        return {"detail": "Genitourinary women exam updated successfully", "record_id": record_id}
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Error updating genitourinary women exam")
    finally:
        db.close()

@router.get("/{record_id}/exams/genitourinary/men", tags=["Medical Records - Genitourinario Hombres"])
async def get_genitourinary_men_exam(
    record_id: str,
    current_user: UserSchema = Depends(require_active_user)
):
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        _check_record_access(current_user, record_id, db)
        
        exam = db.execute(
            text("""
                SELECT id, record_id, disorder_mammary, disorder_testicular
                FROM medical_record_exams_genitourinario_mens
                WHERE record_id = :rid
                LIMIT 1
            """),
            {"rid": record_id}
        ).mappings().first()
        
        if not exam:
            return {"detail": "No genitourinary men exam found", "record_id": record_id}
        
        return {
            "id": exam["id"],
            "record_id": exam["record_id"],
            "disorder_mammary": exam["disorder_mammary"],
            "disorder_testicular": exam["disorder_testicular"],
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error fetching genitourinary men exam")
    finally:
        db.close()


@router.patch("/{record_id}/exams/genitourinary/men", tags=["Medical Records - Genitourinario Hombres"])
async def update_genitourinary_men_exam(
    record_id: str,
    disorder_mammary: int = Form(default=None),
    disorder_testicular: int = Form(default=None),
    current_user: UserSchema = Depends(require_roles("professional", "admin"))
):
    """C.11.2) Crear/Actualizar examen genitourinario (hombres)"""
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        record = db.execute(
            text("SELECT created_by_user_id FROM medical_records WHERE id = :rid"),
            {"rid": record_id}
        ).mappings().first()
        
        if not record:
            raise HTTPException(status_code=404, detail="Medical record not found")
        
        if current_user.role != "admin" and record["created_by_user_id"] != current_user.id:
            raise HTTPException(status_code=403, detail="You can only modify your own records")
        
        exam = db.execute(
            text("SELECT id FROM medical_record_exams_genitourinario_mens WHERE record_id = :rid"),
            {"rid": record_id}
        ).mappings().first()
        
        if exam:
            updates = []
            params: dict[str, Any] = {"record_id": record_id}
            
            if disorder_mammary is not None:
                updates.append("disorder_mammary = :disorder_mammary")
                params["disorder_mammary"] = disorder_mammary
            if disorder_testicular is not None:
                updates.append("disorder_testicular = :disorder_testicular")
                params["disorder_testicular"] = disorder_testicular
            
            if updates:
                db.execute(
                    text(f"UPDATE medical_record_exams_genitourinario_mens SET {', '.join(updates)} WHERE record_id = :record_id"),
                    params
                )
        else:
            exam_id = str(uuid.uuid4())
            db.execute(text("""
                INSERT INTO medical_record_exams_genitourinario_mens
                (id, record_id, disorder_mammary, disorder_testicular)
                VALUES (:id, :record_id, :disorder_mammary, :disorder_testicular)
            """), {
                "id": exam_id,
                "record_id": record_id,
                "disorder_mammary": disorder_mammary,
                "disorder_testicular": disorder_testicular,
            })
        
        db.commit()
        return {"detail": "Genitourinary men exam updated successfully", "record_id": record_id}
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Error updating genitourinary men exam")
    finally:
        db.close()

@router.get("/{record_id}/immunizations", tags=["Medical Records - Inmunizaciones"])
async def get_immunizations(
    record_id: str,
    current_user: UserSchema = Depends(require_active_user)
):
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        _check_record_access(current_user, record_id, db)
        
        imm = db.execute(
            text("""
                SELECT id, record_id, vaccine_sars_cov2, vaccine_fha, vaccine_tdap,
                       vaccine_hep_a, vaccine_hep_b
                FROM medical_record_immunizations
                WHERE record_id = :rid
                LIMIT 1
            """),
            {"rid": record_id}
        ).mappings().first()
        
        if not imm:
            return {"detail": "No immunizations found", "record_id": record_id}
        
        return {
            "id": imm["id"],
            "record_id": imm["record_id"],
            "vaccine_sars_cov2": imm["vaccine_sars_cov2"],
            "vaccine_fha": imm["vaccine_fha"],
            "vaccine_tdap": imm["vaccine_tdap"],
            "vaccine_hep_a": imm["vaccine_hep_a"],
            "vaccine_hep_b": imm["vaccine_hep_b"],
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error fetching immunizations")
    finally:
        db.close()


@router.patch("/{record_id}/immunizations", tags=["Medical Records - Inmunizaciones"])
async def update_immunizations(
    record_id: str,
    vaccine_sars_cov2: int = Form(default=None),
    vaccine_fha: int = Form(default=None),
    vaccine_tdap: int = Form(default=None),
    vaccine_hep_a: int = Form(default=None),
    vaccine_hep_b: int = Form(default=None),
    current_user: UserSchema = Depends(require_roles("professional", "admin"))
):
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        record = db.execute(
            text("SELECT created_by_user_id FROM medical_records WHERE id = :rid"),
            {"rid": record_id}
        ).mappings().first()
        
        if not record:
            raise HTTPException(status_code=404, detail="Medical record not found")
        
        if current_user.role != "admin" and record["created_by_user_id"] != current_user.id:
            raise HTTPException(status_code=403, detail="You can only modify your own records")
        
        imm = db.execute(
            text("SELECT id FROM medical_record_immunizations WHERE record_id = :rid"),
            {"rid": record_id}
        ).mappings().first()
        
        if imm:
            updates = []
            params: dict[str, Any] = {"record_id": record_id}
            
            if vaccine_sars_cov2 is not None:
                updates.append("vaccine_sars_cov2 = :vaccine_sars_cov2")
                params["vaccine_sars_cov2"] = vaccine_sars_cov2
            if vaccine_fha is not None:
                updates.append("vaccine_fha = :vaccine_fha")
                params["vaccine_fha"] = vaccine_fha
            if vaccine_tdap is not None:
                updates.append("vaccine_tdap = :vaccine_tdap")
                params["vaccine_tdap"] = vaccine_tdap
            if vaccine_hep_a is not None:
                updates.append("vaccine_hep_a = :vaccine_hep_a")
                params["vaccine_hep_a"] = vaccine_hep_a
            if vaccine_hep_b is not None:
                updates.append("vaccine_hep_b = :vaccine_hep_b")
                params["vaccine_hep_b"] = vaccine_hep_b
            
            if updates:
                db.execute(
                    text(f"UPDATE medical_record_immunizations SET {', '.join(updates)} WHERE record_id = :record_id"),
                    params
                )
        else:
            imm_id = str(uuid.uuid4())
            db.execute(text("""
                INSERT INTO medical_record_immunizations
                (id, record_id, vaccine_sars_cov2, vaccine_fha, vaccine_tdap, vaccine_hep_a, vaccine_hep_b)
                VALUES (:id, :record_id, :vaccine_sars_cov2, :vaccine_fha, :vaccine_tdap, :vaccine_hep_a, :vaccine_hep_b)
            """), {
                "id": imm_id,
                "record_id": record_id,
                "vaccine_sars_cov2": vaccine_sars_cov2,
                "vaccine_fha": vaccine_fha,
                "vaccine_tdap": vaccine_tdap,
                "vaccine_hep_a": vaccine_hep_a,
                "vaccine_hep_b": vaccine_hep_b,
            })
        
        db.commit()
        return {"detail": "Immunizations updated successfully", "record_id": record_id}
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Error updating immunizations")
    finally:
        db.close()

@router.get("/{record_id}/exposures", tags=["Medical Records - Exposiciones"])
async def get_exposures(
    record_id: str,
    current_user: UserSchema = Depends(require_active_user)
):
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        _check_record_access(current_user, record_id, db)
        
        exp = db.execute(
            text("""
                SELECT id, record_id, exposure_dust, exposure_noise, exposure_animals,
                       exposure_chemicals, exposure_radiation, exposure_other, exposure_other_detail,
                       exposure_approx_date
                FROM medical_record_exposures
                WHERE record_id = :rid
                LIMIT 1
            """),
            {"rid": record_id}
        ).mappings().first()
        
        if not exp:
            return {"detail": "No exposures found", "record_id": record_id}
        
        return {
            "id": exp["id"],
            "record_id": exp["record_id"],
            "exposure_dust": exp["exposure_dust"],
            "exposure_noise": exp["exposure_noise"],
            "exposure_animals": exp["exposure_animals"],
            "exposure_chemicals": exp["exposure_chemicals"],
            "exposure_radiation": exp["exposure_radiation"],
            "exposure_other": exp["exposure_other"],
            "exposure_other_detail": exp["exposure_other_detail"],
            "exposure_approx_date": exp["exposure_approx_date"],
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error fetching exposures")
    finally:
        db.close()

@router.patch("/{record_id}/exposures", tags=["Medical Records - Exposiciones"])
async def update_exposures(
    record_id: str,
    exposure_dust: int = Form(default=None),
    exposure_noise: int = Form(default=None),
    exposure_animals: int = Form(default=None),
    exposure_chemicals: int = Form(default=None),
    exposure_radiation: int = Form(default=None),
    exposure_other: int = Form(default=None),
    exposure_other_detail: str = Form(default=None),
    exposure_approx_date: str = Form(default=None),
    current_user: UserSchema = Depends(require_roles("professional", "admin"))
):
    """C.13.2) Crear/Actualizar exposiciones ocupacionales"""
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        record = db.execute(
            text("SELECT created_by_user_id FROM medical_records WHERE id = :rid"),
            {"rid": record_id}
        ).mappings().first()
        
        if not record:
            raise HTTPException(status_code=404, detail="Medical record not found")
        
        if current_user.role != "admin" and record["created_by_user_id"] != current_user.id:
            raise HTTPException(status_code=403, detail="You can only modify your own records")
        
        exp = db.execute(
            text("SELECT id FROM medical_record_exposures WHERE record_id = :rid"),
            {"rid": record_id}
        ).mappings().first()
        
        if exp:
            updates = []
            params: dict[str, Any] = {"record_id": record_id}
            
            if exposure_dust is not None:
                updates.append("exposure_dust = :exposure_dust")
                params["exposure_dust"] = exposure_dust
            if exposure_noise is not None:
                updates.append("exposure_noise = :exposure_noise")
                params["exposure_noise"] = exposure_noise
            if exposure_animals is not None:
                updates.append("exposure_animals = :exposure_animals")
                params["exposure_animals"] = exposure_animals
            if exposure_chemicals is not None:
                updates.append("exposure_chemicals = :exposure_chemicals")
                params["exposure_chemicals"] = exposure_chemicals
            if exposure_radiation is not None:
                updates.append("exposure_radiation = :exposure_radiation")
                params["exposure_radiation"] = exposure_radiation
            if exposure_other is not None:
                updates.append("exposure_other = :exposure_other")
                params["exposure_other"] = exposure_other
            if exposure_other_detail is not None:
                updates.append("exposure_other_detail = :exposure_other_detail")
                params["exposure_other_detail"] = exposure_other_detail
            if exposure_approx_date is not None:
                updates.append("exposure_approx_date = :exposure_approx_date")
                params["exposure_approx_date"] = exposure_approx_date
            
            if updates:
                db.execute(
                    text(f"UPDATE medical_record_exposures SET {', '.join(updates)} WHERE record_id = :record_id"),
                    params
                )
        else:
            exp_id = str(uuid.uuid4())
            db.execute(text("""
                INSERT INTO medical_record_exposures
                (id, record_id, exposure_dust, exposure_noise, exposure_animals, exposure_chemicals,
                 exposure_radiation, exposure_other, exposure_other_detail, exposure_approx_date)
                VALUES (:id, :record_id, :exposure_dust, :exposure_noise, :exposure_animals, :exposure_chemicals,
                 :exposure_radiation, :exposure_other, :exposure_other_detail, :exposure_approx_date)
            """), {
                "id": exp_id,
                "record_id": record_id,
                "exposure_dust": exposure_dust,
                "exposure_noise": exposure_noise,
                "exposure_animals": exposure_animals,
                "exposure_chemicals": exposure_chemicals,
                "exposure_radiation": exposure_radiation,
                "exposure_other": exposure_other,
                "exposure_other_detail": exposure_other_detail,
                "exposure_approx_date": exposure_approx_date,
            })
        
        db.commit()
        return {"detail": "Exposures updated successfully", "record_id": record_id}
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Error updating exposures")
    finally:
        db.close()

@router.get("/{record_id}/conclusions", tags=["Medical Records - Conclusiones"])
async def get_conclusions(
    record_id: str,
    current_user: UserSchema = Depends(require_active_user)
):
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        _check_record_access(current_user, record_id, db)
        
        record = db.execute(
            text("""
                SELECT id, fitness_result, fitness_duration, fitness_observations
                FROM medical_records
                WHERE id = :rid
                LIMIT 1
            """),
            {"rid": record_id}
        ).mappings().first()
        
        if not record:
            return {"detail": "No conclusions found", "record_id": record_id}
        
        return {
            "record_id": record_id,
            "fitness_result": record["fitness_result"],
            "fitness_duration": record["fitness_duration"],
            "fitness_observations": record["fitness_observations"],
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error fetching conclusions")
    finally:
        db.close()


@router.patch("/{record_id}/conclusions", tags=["Medical Records - Conclusiones"])
async def update_conclusions(
    record_id: str,
    fitness_result: str = Form(default=None),
    fitness_duration: str = Form(default=None),
    fitness_observations: str = Form(default=None),
    current_user: UserSchema = Depends(require_roles("professional", "admin"))
):
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        record = db.execute(
            text("SELECT created_by_user_id FROM medical_records WHERE id = :rid"),
            {"rid": record_id}
        ).mappings().first()
        
        if not record:
            raise HTTPException(status_code=404, detail="Medical record not found")
        
        if current_user.role != "admin" and record["created_by_user_id"] != current_user.id:
            raise HTTPException(status_code=403, detail="You can only modify your own records")
        
        updates = []
        params = {"record_id": record_id}
        
        if fitness_result is not None:
            updates.append("fitness_result = :fitness_result")
            params["fitness_result"] = fitness_result
        if fitness_duration is not None:
            updates.append("fitness_duration = :fitness_duration")
            params["fitness_duration"] = fitness_duration
        if fitness_observations is not None:
            updates.append("fitness_observations = :fitness_observations")
            params["fitness_observations"] = fitness_observations
        
        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")
        
        db.execute(
            text(f"UPDATE medical_records SET {', '.join(updates)} WHERE id = :record_id"),
            params
        )
        
        db.commit()
        return {"detail": "Conclusions updated successfully", "record_id": record_id}
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Error updating conclusions")
    finally:
        db.close()

@router.get("/{record_id}/occupational-history", tags=["Medical Records - Historial Ocupacional"])
async def list_occupational_history(
    record_id: str,
    current_user: UserSchema = Depends(require_active_user)
):
    """D.1.1) Listar historial ocupacional (items)"""
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        _check_record_access(current_user, record_id, db)
        
        items = db.execute(
            text("""
                SELECT id, record_id, job_title, company_name, duration_years, exposures,
                       health_incidents, observations, created_at
                FROM occupational_history_entries
                WHERE record_id = :rid
                ORDER BY created_at DESC
            """),
            {"rid": record_id}
        ).mappings().all()
        
        return {
            "record_id": record_id,
            "items": [dict(row) for row in items],
            "total": len(items)
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error fetching occupational history")
    finally:
        db.close()


@router.post("/{record_id}/occupational-history", tags=["Medical Records - Historial Ocupacional"])
async def create_occupational_history_item(
    record_id: str,
    job_title: str = Form(...),
    company_name: str = Form(...),
    duration_years: float = Form(...),
    exposures: str = Form(default=""),
    health_incidents: str = Form(default=""),
    observations: str = Form(default=""),
    current_user: UserSchema = Depends(require_roles("professional", "admin"))
):
    """D.1.2) Crear item de historial ocupacional"""
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        record = db.execute(
            text("SELECT created_by_user_id FROM medical_records WHERE id = :rid"),
            {"rid": record_id}
        ).mappings().first()
        
        if not record:
            raise HTTPException(status_code=404, detail="Medical record not found")
        
        if current_user.role != "admin" and record["created_by_user_id"] != current_user.id:
            raise HTTPException(status_code=403, detail="You can only modify your own records")
        
        item_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        
        db.execute(text("""
            INSERT INTO occupational_history_entries
            (id, record_id, job_title, company_name, duration_years, exposures, health_incidents, observations, created_at)
            VALUES (:id, :record_id, :job_title, :company_name, :duration_years, :exposures, :health_incidents, :observations, :created_at)
        """), {
            "id": item_id,
            "record_id": record_id,
            "job_title": job_title,
            "company_name": company_name,
            "duration_years": duration_years,
            "exposures": exposures,
            "health_incidents": health_incidents,
            "observations": observations,
            "created_at": now,
        })
        
        db.commit()
        return {
            "detail": "Occupational history item created successfully",
            "record_id": record_id,
            "item_id": item_id
        }
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Error creating occupational history item")
    finally:
        db.close()


@router.patch("/{record_id}/occupational-history/{item_id}", tags=["Medical Records - Historial Ocupacional"])
async def update_occupational_history_item(
    record_id: str,
    item_id: str,
    job_title: str = Form(default=None),
    company_name: str = Form(default=None),
    duration_years: float = Form(default=None),
    exposures: str = Form(default=None),
    health_incidents: str = Form(default=None),
    observations: str = Form(default=None),
    current_user: UserSchema = Depends(require_roles("professional", "admin"))
):
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        record = db.execute(
            text("SELECT created_by_user_id FROM medical_records WHERE id = :rid"),
            {"rid": record_id}
        ).mappings().first()
        
        if not record:
            raise HTTPException(status_code=404, detail="Medical record not found")
        
        if current_user.role != "admin" and record["created_by_user_id"] != current_user.id:
            raise HTTPException(status_code=403, detail="You can only modify your own records")
        
        item = db.execute(
            text("SELECT id FROM occupational_history_entries WHERE id = :iid AND record_id = :rid"),
            {"iid": item_id, "rid": record_id}
        ).mappings().first()
        
        if not item:
            raise HTTPException(status_code=404, detail="Occupational history item not found")
        
        updates = []
        params: dict[str, Any] = {"item_id": item_id, "record_id": record_id}
        
        if job_title is not None:
            updates.append("job_title = :job_title")
            params["job_title"] = job_title
        if company_name is not None:
            updates.append("company_name = :company_name")
            params["company_name"] = company_name
        if duration_years is not None:
            updates.append("duration_years = :duration_years")
            params["duration_years"] = duration_years
        if exposures is not None:
            updates.append("exposures = :exposures")
            params["exposures"] = exposures
        if health_incidents is not None:
            updates.append("health_incidents = :health_incidents")
            params["health_incidents"] = health_incidents
        if observations is not None:
            updates.append("observations = :observations")
            params["observations"] = observations
        
        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")
        
        db.execute(
            text(f"UPDATE occupational_history_entries SET {', '.join(updates)} WHERE id = :item_id AND record_id = :record_id"),
            params
        )
        
        db.commit()
        return {"detail": "Occupational history item updated successfully", "record_id": record_id, "item_id": item_id}
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Error updating occupational history item")
    finally:
        db.close()


@router.delete("/{record_id}/occupational-history/{item_id}", tags=["Medical Records - Historial Ocupacional"])
async def delete_occupational_history_item(
    record_id: str,
    item_id: str,
    current_user: UserSchema = Depends(require_roles("professional", "admin"))
):
    """D.1.4) Eliminar item de historial ocupacional"""
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        record = db.execute(
            text("SELECT created_by_user_id FROM medical_records WHERE id = :rid"),
            {"rid": record_id}
        ).mappings().first()
        
        if not record:
            raise HTTPException(status_code=404, detail="Medical record not found")
        
        if current_user.role != "admin" and record["created_by_user_id"] != current_user.id:
            raise HTTPException(status_code=403, detail="You can only modify your own records")
        
        item = db.execute(
            text("SELECT id FROM occupational_history_entries WHERE id = :iid AND record_id = :rid"),
            {"iid": item_id, "rid": record_id}
        ).mappings().first()
        
        if not item:
            raise HTTPException(status_code=404, detail="Occupational history item not found")
        
        db.execute(
            text("DELETE FROM occupational_history_entries WHERE id = :iid AND record_id = :rid"),
            {"iid": item_id, "rid": record_id}
        )
        
        db.commit()
        return {"detail": "Occupational history item deleted successfully", "record_id": record_id, "item_id": item_id}
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Error deleting occupational history item")
    finally:
        db.close()

@router.get("/{record_id}/symptoms", tags=["Medical Records - Síntomas"])
async def get_symptoms(
    record_id: str,
    current_user: UserSchema = Depends(require_active_user)
):
    """D.2.1) Obtener síntomas"""
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        _check_record_access(current_user, record_id, db)
        
        symp = db.execute(
            text("""
                SELECT id, record_id, symptom_description, symptom_duration, 
                       symptom_intensity, related_work
                FROM medical_record_symptoms
                WHERE record_id = :rid
                LIMIT 1
            """),
            {"rid": record_id}
        ).mappings().first()
        
        if not symp:
            return {"detail": "No symptoms found", "record_id": record_id}
        
        return {
            "id": symp["id"],
            "record_id": symp["record_id"],
            "symptom_description": symp["symptom_description"],
            "symptom_duration": symp["symptom_duration"],
            "symptom_intensity": symp["symptom_intensity"],
            "related_work": symp["related_work"],
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error fetching symptoms")
    finally:
        db.close()


@router.patch("/{record_id}/symptoms", tags=["Medical Records - Síntomas"])
async def update_symptoms(
    record_id: str,
    symptom_description: str = Form(default=None),
    symptom_duration: str = Form(default=None),
    symptom_intensity: str = Form(default=None),
    related_work: int = Form(default=None),
    current_user: UserSchema = Depends(require_roles("professional", "admin"))
):
    """D.2.2) Crear/Actualizar síntomas"""
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        record = db.execute(
            text("SELECT created_by_user_id FROM medical_records WHERE id = :rid"),
            {"rid": record_id}
        ).mappings().first()
        
        if not record:
            raise HTTPException(status_code=404, detail="Medical record not found")
        
        if current_user.role != "admin" and record["created_by_user_id"] != current_user.id:
            raise HTTPException(status_code=403, detail="You can only modify your own records")
        
        symp = db.execute(
            text("SELECT id FROM medical_record_symptoms WHERE record_id = :rid"),
            {"rid": record_id}
        ).mappings().first()
        
        if symp:
            updates = []
            params: dict[str, Any] = {"record_id": record_id}
            
            if symptom_description is not None:
                updates.append("symptom_description = :symptom_description")
                params["symptom_description"] = symptom_description
            if symptom_duration is not None:
                updates.append("symptom_duration = :symptom_duration")
                params["symptom_duration"] = symptom_duration
            if symptom_intensity is not None:
                updates.append("symptom_intensity = :symptom_intensity")
                params["symptom_intensity"] = symptom_intensity
            if related_work is not None:
                updates.append("related_work = :related_work")
                params["related_work"] = related_work
            
            if updates:
                db.execute(
                    text(f"UPDATE medical_record_symptoms SET {', '.join(updates)} WHERE record_id = :record_id"),
                    params
                )
        else:
            symp_id = str(uuid.uuid4())
            db.execute(text("""
                INSERT INTO medical_record_symptoms
                (id, record_id, symptom_description, symptom_duration, symptom_intensity, related_work)
                VALUES (:id, :record_id, :symptom_description, :symptom_duration, :symptom_intensity, :related_work)
            """), {
                "id": symp_id,
                "record_id": record_id,
                "symptom_description": symptom_description,
                "symptom_duration": symptom_duration,
                "symptom_intensity": symptom_intensity,
                "related_work": related_work,
            })
        
        db.commit()
        return {"detail": "Symptoms updated successfully", "record_id": record_id}
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Error updating symptoms")
    finally:
        db.close()

@router.get("/{record_id}/work-risks", tags=["Medical Records - Riesgos Laborales"])
async def get_work_risks(
    record_id: str,
    current_user: UserSchema = Depends(require_active_user)
):
    """D.3.1) Obtener riesgos laborales"""
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        _check_record_access(current_user, record_id, db)
        
        risk = db.execute(
            text("""
                SELECT id, record_id, risk_description, risk_level, 
                       control_measures, observations
                FROM medical_record_work_risks
                WHERE record_id = :rid
                LIMIT 1
            """),
            {"rid": record_id}
        ).mappings().first()
        
        if not risk:
            return {"detail": "No work risks found", "record_id": record_id}
        
        return {
            "id": risk["id"],
            "record_id": risk["record_id"],
            "risk_description": risk["risk_description"],
            "risk_level": risk["risk_level"],
            "control_measures": risk["control_measures"],
            "observations": risk["observations"],
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error fetching work risks")
    finally:
        db.close()


@router.patch("/{record_id}/work-risks", tags=["Medical Records - Riesgos Laborales"])
async def update_work_risks(
    record_id: str,
    risk_description: str = Form(default=None),
    risk_level: str = Form(default=None),
    control_measures: str = Form(default=None),
    observations: str = Form(default=None),
    current_user: UserSchema = Depends(require_roles("professional", "admin"))
):
    """D.3.2) Crear/Actualizar riesgos laborales"""
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        record = db.execute(
            text("SELECT created_by_user_id FROM medical_records WHERE id = :rid"),
            {"rid": record_id}
        ).mappings().first()
        
        if not record:
            raise HTTPException(status_code=404, detail="Medical record not found")
        
        if current_user.role != "admin" and record["created_by_user_id"] != current_user.id:
            raise HTTPException(status_code=403, detail="You can only modify your own records")
        
        risk = db.execute(
            text("SELECT id FROM medical_record_work_risks WHERE record_id = :rid"),
            {"rid": record_id}
        ).mappings().first()
        
        if risk:
            updates = []
            params = {"record_id": record_id}
            
            if risk_description is not None:
                updates.append("risk_description = :risk_description")
                params["risk_description"] = risk_description
            if risk_level is not None:
                updates.append("risk_level = :risk_level")
                params["risk_level"] = risk_level
            if control_measures is not None:
                updates.append("control_measures = :control_measures")
                params["control_measures"] = control_measures
            if observations is not None:
                updates.append("observations = :observations")
                params["observations"] = observations
            
            if updates:
                db.execute(
                    text(f"UPDATE medical_record_work_risks SET {', '.join(updates)} WHERE record_id = :record_id"),
                    params
                )
        else:
            risk_id = str(uuid.uuid4())
            db.execute(text("""
                INSERT INTO medical_record_work_risks
                (id, record_id, risk_description, risk_level, control_measures, observations)
                VALUES (:id, :record_id, :risk_description, :risk_level, :control_measures, :observations)
            """), {
                "id": risk_id,
                "record_id": record_id,
                "risk_description": risk_description,
                "risk_level": risk_level,
                "control_measures": control_measures,
                "observations": observations,
            })
        
        db.commit()
        return {"detail": "Work risks updated successfully", "record_id": record_id}
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Error updating work risks")
    finally:
        db.close()

@router.get("/{record_id}/surgeries", tags=["Medical Records - Cirugías"])
async def get_surgeries(
    record_id: str,
    current_user: UserSchema = Depends(require_active_user)
):
    """D.4.1) Obtener cirugías"""
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        _check_record_access(current_user, record_id, db)
        
        surg = db.execute(
            text("""
                SELECT id, record_id, surgery_abdomen, surgery_thorax, surgery_extremities,
                       surgery_head_neck, surgery_cardiovascular, surgery_gynecological,
                       surgery_other, surgery_observations
                FROM medical_record_surgeries
                WHERE record_id = :rid
                LIMIT 1
            """),
            {"rid": record_id}
        ).mappings().first()
        
        if not surg:
            return {"detail": "No surgeries found", "record_id": record_id}
        
        return {
            "id": surg["id"],
            "record_id": surg["record_id"],
            "surgery_abdomen": surg["surgery_abdomen"],
            "surgery_thorax": surg["surgery_thorax"],
            "surgery_extremities": surg["surgery_extremities"],
            "surgery_head_neck": surg["surgery_head_neck"],
            "surgery_cardiovascular": surg["surgery_cardiovascular"],
            "surgery_gynecological": surg["surgery_gynecological"],
            "surgery_other": surg["surgery_other"],
            "surgery_observations": surg["surgery_observations"],
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error fetching surgeries")
    finally:
        db.close()


@router.patch("/{record_id}/surgeries", tags=["Medical Records - Cirugías"])
async def update_surgeries(
    record_id: str,
    surgery_abdomen: int = Form(default=None),
    surgery_thorax: int = Form(default=None),
    surgery_extremities: int = Form(default=None),
    surgery_head_neck: int = Form(default=None),
    surgery_cardiovascular: int = Form(default=None),
    surgery_gynecological: int = Form(default=None),
    surgery_other: int = Form(default=None),
    surgery_observations: str = Form(default=None),
    current_user: UserSchema = Depends(require_roles("professional", "admin"))
):
    """D.4.2) Crear/Actualizar cirugías"""
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        record = db.execute(
            text("SELECT created_by_user_id FROM medical_records WHERE id = :rid"),
            {"rid": record_id}
        ).mappings().first()
        
        if not record:
            raise HTTPException(status_code=404, detail="Medical record not found")
        
        if current_user.role != "admin" and record["created_by_user_id"] != current_user.id:
            raise HTTPException(status_code=403, detail="You can only modify your own records")
        
        surg = db.execute(
            text("SELECT id FROM medical_record_surgeries WHERE record_id = :rid"),
            {"rid": record_id}
        ).mappings().first()
        
        if surg:
            updates = []
            params: dict[str, Any] = {"record_id": record_id}
            
            if surgery_abdomen is not None:
                updates.append("surgery_abdomen = :surgery_abdomen")
                params["surgery_abdomen"] = surgery_abdomen
            if surgery_thorax is not None:
                updates.append("surgery_thorax = :surgery_thorax")
                params["surgery_thorax"] = surgery_thorax
            if surgery_extremities is not None:
                updates.append("surgery_extremities = :surgery_extremities")
                params["surgery_extremities"] = surgery_extremities
            if surgery_head_neck is not None:
                updates.append("surgery_head_neck = :surgery_head_neck")
                params["surgery_head_neck"] = surgery_head_neck
            if surgery_cardiovascular is not None:
                updates.append("surgery_cardiovascular = :surgery_cardiovascular")
                params["surgery_cardiovascular"] = surgery_cardiovascular
            if surgery_gynecological is not None:
                updates.append("surgery_gynecological = :surgery_gynecological")
                params["surgery_gynecological"] = surgery_gynecological
            if surgery_other is not None:
                updates.append("surgery_other = :surgery_other")
                params["surgery_other"] = surgery_other
            if surgery_observations is not None:
                updates.append("surgery_observations = :surgery_observations")
                params["surgery_observations"] = surgery_observations
            
            if updates:
                db.execute(
                    text(f"UPDATE medical_record_surgeries SET {', '.join(updates)} WHERE record_id = :record_id"),
                    params
                )
        else:
            surg_id = str(uuid.uuid4())
            db.execute(text("""
                INSERT INTO medical_record_surgeries
                (id, record_id, surgery_abdomen, surgery_thorax, surgery_extremities, surgery_head_neck,
                 surgery_cardiovascular, surgery_gynecological, surgery_other, surgery_observations)
                VALUES (:id, :record_id, :surgery_abdomen, :surgery_thorax, :surgery_extremities, :surgery_head_neck,
                 :surgery_cardiovascular, :surgery_gynecological, :surgery_other, :surgery_observations)
            """), {
                "id": surg_id,
                "record_id": record_id,
                "surgery_abdomen": surgery_abdomen,
                "surgery_thorax": surgery_thorax,
                "surgery_extremities": surgery_extremities,
                "surgery_head_neck": surgery_head_neck,
                "surgery_cardiovascular": surgery_cardiovascular,
                "surgery_gynecological": surgery_gynecological,
                "surgery_other": surgery_other,
                "surgery_observations": surgery_observations,
            })
        
        db.commit()
        return {"detail": "Surgeries updated successfully", "record_id": record_id}
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Error updating surgeries")
    finally:
        db.close()

@router.get("/{record_id}/personal-history", tags=["Medical Records - Historial Personal"])
async def get_personal_history(
    record_id: str,
    current_user: UserSchema = Depends(require_active_user)
):
    """E.1.1) Obtener historial personal"""
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        _check_record_access(current_user, record_id, db)
        
        history = db.execute(
            text("""
                SELECT id, record_id, allergies, blood_type, medication_history, 
                       medical_conditions, surgeries_history, mental_health, other_conditions
                FROM medical_record_personal_history
                WHERE record_id = :rid
                LIMIT 1
            """),
            {"rid": record_id}
        ).mappings().first()
        
        if not history:
            return {"detail": "No personal history found", "record_id": record_id}
        
        return {
            "id": history["id"],
            "record_id": history["record_id"],
            "allergies": history["allergies"],
            "blood_type": history["blood_type"],
            "medication_history": history["medication_history"],
            "medical_conditions": history["medical_conditions"],
            "surgeries_history": history["surgeries_history"],
            "mental_health": history["mental_health"],
            "other_conditions": history["other_conditions"],
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error fetching personal history")
    finally:
        db.close()


@router.patch("/{record_id}/personal-history", tags=["Medical Records - Historial Personal"])
async def update_personal_history(
    record_id: str,
    allergies: str = Form(default=None),
    blood_type: str = Form(default=None),
    medication_history: str = Form(default=None),
    medical_conditions: str = Form(default=None),
    surgeries_history: str = Form(default=None),
    mental_health: str = Form(default=None),
    other_conditions: str = Form(default=None),
    current_user: UserSchema = Depends(require_roles("professional", "admin"))
):
    """E.1.2) Crear/Actualizar historial personal"""
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        record = db.execute(
            text("SELECT created_by_user_id FROM medical_records WHERE id = :rid"),
            {"rid": record_id}
        ).mappings().first()
        
        if not record:
            raise HTTPException(status_code=404, detail="Medical record not found")
        
        if current_user.role != "admin" and record["created_by_user_id"] != current_user.id:
            raise HTTPException(status_code=403, detail="You can only modify your own records")
        
        history = db.execute(
            text("SELECT id FROM medical_record_personal_history WHERE record_id = :rid"),
            {"rid": record_id}
        ).mappings().first()
        
        if history:
            updates = []
            params = {"record_id": record_id}
            
            if allergies is not None:
                updates.append("allergies = :allergies")
                params["allergies"] = allergies
            if blood_type is not None:
                updates.append("blood_type = :blood_type")
                params["blood_type"] = blood_type
            if medication_history is not None:
                updates.append("medication_history = :medication_history")
                params["medication_history"] = medication_history
            if medical_conditions is not None:
                updates.append("medical_conditions = :medical_conditions")
                params["medical_conditions"] = medical_conditions
            if surgeries_history is not None:
                updates.append("surgeries_history = :surgeries_history")
                params["surgeries_history"] = surgeries_history
            if mental_health is not None:
                updates.append("mental_health = :mental_health")
                params["mental_health"] = mental_health
            if other_conditions is not None:
                updates.append("other_conditions = :other_conditions")
                params["other_conditions"] = other_conditions
            
            if updates:
                db.execute(
                    text(f"UPDATE medical_record_personal_history SET {', '.join(updates)} WHERE record_id = :record_id"),
                    params
                )
        else:
            history_id = str(uuid.uuid4())
            db.execute(text("""
                INSERT INTO medical_record_personal_history
                (id, record_id, allergies, blood_type, medication_history, medical_conditions, 
                 surgeries_history, mental_health, other_conditions)
                VALUES (:id, :record_id, :allergies, :blood_type, :medication_history, :medical_conditions,
                 :surgeries_history, :mental_health, :other_conditions)
            """), {
                "id": history_id,
                "record_id": record_id,
                "allergies": allergies,
                "blood_type": blood_type,
                "medication_history": medication_history,
                "medical_conditions": medical_conditions,
                "surgeries_history": surgeries_history,
                "mental_health": mental_health,
                "other_conditions": other_conditions,
            })
        
        db.commit()
        return {"detail": "Personal history updated successfully", "record_id": record_id}
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Error updating personal history")
    finally:
        db.close()

@router.get("/{record_id}/family-history", tags=["Medical Records - Historial Familiar"])
async def get_family_history(
    record_id: str,
    current_user: UserSchema = Depends(require_active_user)
):
    """E.2.1) Obtener historial familiar"""
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        _check_record_access(current_user, record_id, db)
        
        history = db.execute(
            text("""
                SELECT id, record_id, parents_diseases, siblings_diseases, 
                       partner_diseases, children_diseases, hereditary_conditions, family_observations
                FROM medical_record_family_history
                WHERE record_id = :rid
                LIMIT 1
            """),
            {"rid": record_id}
        ).mappings().first()
        
        if not history:
            return {"detail": "No family history found", "record_id": record_id}
        
        return {
            "id": history["id"],
            "record_id": history["record_id"],
            "parents_diseases": history["parents_diseases"],
            "siblings_diseases": history["siblings_diseases"],
            "partner_diseases": history["partner_diseases"],
            "children_diseases": history["children_diseases"],
            "hereditary_conditions": history["hereditary_conditions"],
            "family_observations": history["family_observations"],
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error fetching family history")
    finally:
        db.close()


@router.patch("/{record_id}/family-history", tags=["Medical Records - Historial Familiar"])
async def update_family_history(
    record_id: str,
    parents_diseases: str = Form(default=None),
    siblings_diseases: str = Form(default=None),
    partner_diseases: str = Form(default=None),
    children_diseases: str = Form(default=None),
    hereditary_conditions: str = Form(default=None),
    family_observations: str = Form(default=None),
    current_user: UserSchema = Depends(require_roles("professional", "admin"))
):
    """E.2.2) Crear/Actualizar historial familiar"""
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        record = db.execute(
            text("SELECT created_by_user_id FROM medical_records WHERE id = :rid"),
            {"rid": record_id}
        ).mappings().first()
        
        if not record:
            raise HTTPException(status_code=404, detail="Medical record not found")
        
        if current_user.role != "admin" and record["created_by_user_id"] != current_user.id:
            raise HTTPException(status_code=403, detail="You can only modify your own records")
        
        history = db.execute(
            text("SELECT id FROM medical_record_family_history WHERE record_id = :rid"),
            {"rid": record_id}
        ).mappings().first()
        
        if history:
            updates = []
            params = {"record_id": record_id}
            
            if parents_diseases is not None:
                updates.append("parents_diseases = :parents_diseases")
                params["parents_diseases"] = parents_diseases
            if siblings_diseases is not None:
                updates.append("siblings_diseases = :siblings_diseases")
                params["siblings_diseases"] = siblings_diseases
            if partner_diseases is not None:
                updates.append("partner_diseases = :partner_diseases")
                params["partner_diseases"] = partner_diseases
            if children_diseases is not None:
                updates.append("children_diseases = :children_diseases")
                params["children_diseases"] = children_diseases
            if hereditary_conditions is not None:
                updates.append("hereditary_conditions = :hereditary_conditions")
                params["hereditary_conditions"] = hereditary_conditions
            if family_observations is not None:
                updates.append("family_observations = :family_observations")
                params["family_observations"] = family_observations
            
            if updates:
                db.execute(
                    text(f"UPDATE medical_record_family_history SET {', '.join(updates)} WHERE record_id = :record_id"),
                    params
                )
        else:
            history_id = str(uuid.uuid4())
            db.execute(text("""
                INSERT INTO medical_record_family_history
                (id, record_id, parents_diseases, siblings_diseases, partner_diseases, 
                 children_diseases, hereditary_conditions, family_observations)
                VALUES (:id, :record_id, :parents_diseases, :siblings_diseases, :partner_diseases,
                 :children_diseases, :hereditary_conditions, :family_observations)
            """), {
                "id": history_id,
                "record_id": record_id,
                "parents_diseases": parents_diseases,
                "siblings_diseases": siblings_diseases,
                "partner_diseases": partner_diseases,
                "children_diseases": children_diseases,
                "hereditary_conditions": hereditary_conditions,
                "family_observations": family_observations,
            })
        
        db.commit()
        return {"detail": "Family history updated successfully", "record_id": record_id}
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Error updating family history")
    finally:
        db.close()

@router.get("/{record_id}/habits", tags=["Medical Records - Hábitos"])
async def get_habits(
    record_id: str,
    current_user: UserSchema = Depends(require_active_user)
):
    """E.3.1) Obtener hábitos"""
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        _check_record_access(current_user, record_id, db)
        
        habits = db.execute(
            text("""
                SELECT id, record_id, tobacco_use, tobacco_frequency, tobacco_type, alcohol_use,
                       alcohol_frequency, alcohol_type, drug_use, drug_frequency, drug_type,
                       exercise_frequency, exercise_type, diet_type, sleep_hours, sleep_quality,
                       stress_level, caffeine_use, sexual_practices, hygiene_quality,
                       substance_abuse, substance_type, habits_observations
                FROM medical_record_habits
                WHERE record_id = :rid
                LIMIT 1
            """),
            {"rid": record_id}
        ).mappings().first()
        
        if not habits:
            return {"detail": "No habits found", "record_id": record_id}
        
        return {
            "id": habits["id"],
            "record_id": habits["record_id"],
            "tobacco_use": habits["tobacco_use"],
            "tobacco_frequency": habits["tobacco_frequency"],
            "tobacco_type": habits["tobacco_type"],
            "alcohol_use": habits["alcohol_use"],
            "alcohol_frequency": habits["alcohol_frequency"],
            "alcohol_type": habits["alcohol_type"],
            "drug_use": habits["drug_use"],
            "drug_frequency": habits["drug_frequency"],
            "drug_type": habits["drug_type"],
            "exercise_frequency": habits["exercise_frequency"],
            "exercise_type": habits["exercise_type"],
            "diet_type": habits["diet_type"],
            "sleep_hours": habits["sleep_hours"],
            "sleep_quality": habits["sleep_quality"],
            "stress_level": habits["stress_level"],
            "caffeine_use": habits["caffeine_use"],
            "sexual_practices": habits["sexual_practices"],
            "hygiene_quality": habits["hygiene_quality"],
            "substance_abuse": habits["substance_abuse"],
            "substance_type": habits["substance_type"],
            "habits_observations": habits["habits_observations"],
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error fetching habits")
    finally:
        db.close()


@router.patch("/{record_id}/habits", tags=["Medical Records - Hábitos"])
async def update_habits(
    record_id: str,
    tobacco_use: int = Form(default=None),
    tobacco_frequency: str = Form(default=None),
    tobacco_type: str = Form(default=None),
    alcohol_use: int = Form(default=None),
    alcohol_frequency: str = Form(default=None),
    alcohol_type: str = Form(default=None),
    drug_use: int = Form(default=None),
    drug_frequency: str = Form(default=None),
    drug_type: str = Form(default=None),
    exercise_frequency: str = Form(default=None),
    exercise_type: str = Form(default=None),
    diet_type: str = Form(default=None),
    sleep_hours: int = Form(default=None),
    sleep_quality: str = Form(default=None),
    stress_level: str = Form(default=None),
    caffeine_use: int = Form(default=None),
    sexual_practices: str = Form(default=None),
    hygiene_quality: str = Form(default=None),
    substance_abuse: int = Form(default=None),
    substance_type: str = Form(default=None),
    habits_observations: str = Form(default=None),
    current_user: UserSchema = Depends(require_roles("professional", "admin"))
):
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        record = db.execute(
            text("SELECT created_by_user_id FROM medical_records WHERE id = :rid"),
            {"rid": record_id}
        ).mappings().first()
        
        if not record:
            raise HTTPException(status_code=404, detail="Medical record not found")
        
        if current_user.role != "admin" and record["created_by_user_id"] != current_user.id:
            raise HTTPException(status_code=403, detail="You can only modify your own records")
        
        habits = db.execute(
            text("SELECT id FROM medical_record_habits WHERE record_id = :rid"),
            {"rid": record_id}
        ).mappings().first()
        
        if habits:
            updates = []
            params: dict[str, Any] = {"record_id": record_id}
            
            if tobacco_use is not None:
                updates.append("tobacco_use = :tobacco_use")
                params["tobacco_use"] = tobacco_use
            if tobacco_frequency is not None:
                updates.append("tobacco_frequency = :tobacco_frequency")
                params["tobacco_frequency"] = tobacco_frequency
            if tobacco_type is not None:
                updates.append("tobacco_type = :tobacco_type")
                params["tobacco_type"] = tobacco_type
            if alcohol_use is not None:
                updates.append("alcohol_use = :alcohol_use")
                params["alcohol_use"] = alcohol_use
            if alcohol_frequency is not None:
                updates.append("alcohol_frequency = :alcohol_frequency")
                params["alcohol_frequency"] = alcohol_frequency
            if alcohol_type is not None:
                updates.append("alcohol_type = :alcohol_type")
                params["alcohol_type"] = alcohol_type
            if drug_use is not None:
                updates.append("drug_use = :drug_use")
                params["drug_use"] = drug_use
            if drug_frequency is not None:
                updates.append("drug_frequency = :drug_frequency")
                params["drug_frequency"] = drug_frequency
            if drug_type is not None:
                updates.append("drug_type = :drug_type")
                params["drug_type"] = drug_type
            if exercise_frequency is not None:
                updates.append("exercise_frequency = :exercise_frequency")
                params["exercise_frequency"] = exercise_frequency
            if exercise_type is not None:
                updates.append("exercise_type = :exercise_type")
                params["exercise_type"] = exercise_type
            if diet_type is not None:
                updates.append("diet_type = :diet_type")
                params["diet_type"] = diet_type
            if sleep_hours is not None:
                updates.append("sleep_hours = :sleep_hours")
                params["sleep_hours"] = sleep_hours
            if sleep_quality is not None:
                updates.append("sleep_quality = :sleep_quality")
                params["sleep_quality"] = sleep_quality
            if stress_level is not None:
                updates.append("stress_level = :stress_level")
                params["stress_level"] = stress_level
            if caffeine_use is not None:
                updates.append("caffeine_use = :caffeine_use")
                params["caffeine_use"] = caffeine_use
            if sexual_practices is not None:
                updates.append("sexual_practices = :sexual_practices")
                params["sexual_practices"] = sexual_practices
            if hygiene_quality is not None:
                updates.append("hygiene_quality = :hygiene_quality")
                params["hygiene_quality"] = hygiene_quality
            if substance_abuse is not None:
                updates.append("substance_abuse = :substance_abuse")
                params["substance_abuse"] = substance_abuse
            if substance_type is not None:
                updates.append("substance_type = :substance_type")
                params["substance_type"] = substance_type
            if habits_observations is not None:
                updates.append("habits_observations = :habits_observations")
                params["habits_observations"] = habits_observations
            
            if updates:
                db.execute(
                    text(f"UPDATE medical_record_habits SET {', '.join(updates)} WHERE record_id = :record_id"),
                    params
                )
        else:
            habits_id = str(uuid.uuid4())
            db.execute(text("""
                INSERT INTO medical_record_habits
                (id, record_id, tobacco_use, tobacco_frequency, tobacco_type, alcohol_use, alcohol_frequency,
                 alcohol_type, drug_use, drug_frequency, drug_type, exercise_frequency, exercise_type,
                 diet_type, sleep_hours, sleep_quality, stress_level, caffeine_use, sexual_practices,
                 hygiene_quality, substance_abuse, substance_type, habits_observations)
                VALUES (:id, :record_id, :tobacco_use, :tobacco_frequency, :tobacco_type, :alcohol_use, :alcohol_frequency,
                 :alcohol_type, :drug_use, :drug_frequency, :drug_type, :exercise_frequency, :exercise_type,
                 :diet_type, :sleep_hours, :sleep_quality, :stress_level, :caffeine_use, :sexual_practices,
                 :hygiene_quality, :substance_abuse, :substance_type, :habits_observations)
            """), {
                "id": habits_id,
                "record_id": record_id,
                "tobacco_use": tobacco_use,
                "tobacco_frequency": tobacco_frequency,
                "tobacco_type": tobacco_type,
                "alcohol_use": alcohol_use,
                "alcohol_frequency": alcohol_frequency,
                "alcohol_type": alcohol_type,
                "drug_use": drug_use,
                "drug_frequency": drug_frequency,
                "drug_type": drug_type,
                "exercise_frequency": exercise_frequency,
                "exercise_type": exercise_type,
                "diet_type": diet_type,
                "sleep_hours": sleep_hours,
                "sleep_quality": sleep_quality,
                "stress_level": stress_level,
                "caffeine_use": caffeine_use,
                "sexual_practices": sexual_practices,
                "hygiene_quality": hygiene_quality,
                "substance_abuse": substance_abuse,
                "substance_type": substance_type,
                "habits_observations": habits_observations,
            })
        
        db.commit()
        return {"detail": "Habits updated successfully", "record_id": record_id}
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Error updating habits")
    finally:
        db.close()

@router.get("/{record_id}/performed-studies", tags=["Medical Records - Estudios Realizados"])
async def get_performed_studies(
    record_id: str,
    current_user: UserSchema = Depends(require_active_user)
):
    """E.4.1) Obtener estudios realizados"""
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        _check_record_access(current_user, record_id, db)
        
        studies = db.execute(
            text("""
                SELECT id, record_id, blood_test, chest_xray, ecg, pulmonary_function,
                       audiometry, spirometry, dermatology_screening, gynecology_screening,
                       colonoscopy, ultrasound, ct_scan, mri, other_studies, studies_observations
                FROM medical_record_performed_studies
                WHERE record_id = :rid
                LIMIT 1
            """),
            {"rid": record_id}
        ).mappings().first()
        
        if not studies:
            return {"detail": "No performed studies found", "record_id": record_id}
        
        return {
            "id": studies["id"],
            "record_id": studies["record_id"],
            "blood_test": studies["blood_test"],
            "chest_xray": studies["chest_xray"],
            "ecg": studies["ecg"],
            "pulmonary_function": studies["pulmonary_function"],
            "audiometry": studies["audiometry"],
            "spirometry": studies["spirometry"],
            "dermatology_screening": studies["dermatology_screening"],
            "gynecology_screening": studies["gynecology_screening"],
            "colonoscopy": studies["colonoscopy"],
            "ultrasound": studies["ultrasound"],
            "ct_scan": studies["ct_scan"],
            "mri": studies["mri"],
            "other_studies": studies["other_studies"],
            "studies_observations": studies["studies_observations"],
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error fetching performed studies")
    finally:
        db.close()


@router.patch("/{record_id}/performed-studies", tags=["Medical Records - Estudios Realizados"])
async def update_performed_studies(
    record_id: str,
    blood_test: int = Form(default=None),
    chest_xray: int = Form(default=None),
    ecg: int = Form(default=None),
    pulmonary_function: int = Form(default=None),
    audiometry: int = Form(default=None),
    spirometry: int = Form(default=None),
    dermatology_screening: int = Form(default=None),
    gynecology_screening: int = Form(default=None),
    colonoscopy: int = Form(default=None),
    ultrasound: int = Form(default=None),
    ct_scan: int = Form(default=None),
    mri: int = Form(default=None),
    other_studies: str = Form(default=None),
    studies_observations: str = Form(default=None),
    current_user: UserSchema = Depends(require_roles("professional", "admin"))
):
    """E.4.2) Crear/Actualizar estudios realizados"""
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        record = db.execute(
            text("SELECT created_by_user_id FROM medical_records WHERE id = :rid"),
            {"rid": record_id}
        ).mappings().first()
        
        if not record:
            raise HTTPException(status_code=404, detail="Medical record not found")
        
        if current_user.role != "admin" and record["created_by_user_id"] != current_user.id:
            raise HTTPException(status_code=403, detail="You can only modify your own records")
        
        studies = db.execute(
            text("SELECT id FROM medical_record_performed_studies WHERE record_id = :rid"),
            {"rid": record_id}
        ).mappings().first()
        
        if studies:
            updates = []
            params: dict[str, Any] = {"record_id": record_id}
            
            if blood_test is not None:
                updates.append("blood_test = :blood_test")
                params["blood_test"] = blood_test
            if chest_xray is not None:
                updates.append("chest_xray = :chest_xray")
                params["chest_xray"] = chest_xray
            if ecg is not None:
                updates.append("ecg = :ecg")
                params["ecg"] = ecg
            if pulmonary_function is not None:
                updates.append("pulmonary_function = :pulmonary_function")
                params["pulmonary_function"] = pulmonary_function
            if audiometry is not None:
                updates.append("audiometry = :audiometry")
                params["audiometry"] = audiometry
            if spirometry is not None:
                updates.append("spirometry = :spirometry")
                params["spirometry"] = spirometry
            if dermatology_screening is not None:
                updates.append("dermatology_screening = :dermatology_screening")
                params["dermatology_screening"] = dermatology_screening
            if gynecology_screening is not None:
                updates.append("gynecology_screening = :gynecology_screening")
                params["gynecology_screening"] = gynecology_screening
            if colonoscopy is not None:
                updates.append("colonoscopy = :colonoscopy")
                params["colonoscopy"] = colonoscopy
            if ultrasound is not None:
                updates.append("ultrasound = :ultrasound")
                params["ultrasound"] = ultrasound
            if ct_scan is not None:
                updates.append("ct_scan = :ct_scan")
                params["ct_scan"] = ct_scan
            if mri is not None:
                updates.append("mri = :mri")
                params["mri"] = mri
            if other_studies is not None:
                updates.append("other_studies = :other_studies")
                params["other_studies"] = other_studies
            if studies_observations is not None:
                updates.append("studies_observations = :studies_observations")
                params["studies_observations"] = studies_observations
            
            if updates:
                db.execute(
                    text(f"UPDATE medical_record_performed_studies SET {', '.join(updates)} WHERE record_id = :record_id"),
                    params
                )
        else:
            studies_id = str(uuid.uuid4())
            db.execute(text("""
                INSERT INTO medical_record_performed_studies
                (id, record_id, blood_test, chest_xray, ecg, pulmonary_function, audiometry,
                 spirometry, dermatology_screening, gynecology_screening, colonoscopy, ultrasound,
                 ct_scan, mri, other_studies, studies_observations)
                VALUES (:id, :record_id, :blood_test, :chest_xray, :ecg, :pulmonary_function, :audiometry,
                 :spirometry, :dermatology_screening, :gynecology_screening, :colonoscopy, :ultrasound,
                 :ct_scan, :mri, :other_studies, :studies_observations)
            """), {
                "id": studies_id,
                "record_id": record_id,
                "blood_test": blood_test,
                "chest_xray": chest_xray,
                "ecg": ecg,
                "pulmonary_function": pulmonary_function,
                "audiometry": audiometry,
                "spirometry": spirometry,
                "dermatology_screening": dermatology_screening,
                "gynecology_screening": gynecology_screening,
                "colonoscopy": colonoscopy,
                "ultrasound": ultrasound,
                "ct_scan": ct_scan,
                "mri": mri,
                "other_studies": other_studies,
                "studies_observations": studies_observations,
            })
        
        db.commit()
        return {"detail": "Performed studies updated successfully", "record_id": record_id}
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Error updating performed studies")
    finally:
        db.close()
