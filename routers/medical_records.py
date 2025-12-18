from fastapi import APIRouter, Depends, HTTPException, status, Form
from models.user import User
from auth.authentication import require_active_user, require_roles
from Database.getConnection import getConnectionForLogin
from sqlalchemy import text
from datetime import datetime
import uuid
from typing import Optional

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

def _check_access(current_user: User, record: dict, db):
    if current_user.role == "admin":
        return True
    
    if current_user.role == "professional":
        # Profesional ve sus propios records y todos (para acceso a datos de pacientes)
        return True
    
    if current_user.role == "company":
        # Company owner solo ve records de sus empleados
        company_row = db.execute(
            text("SELECT id FROM companies WHERE owner_user_id = :uid"),
            {"uid": current_user.id}
        ).mappings().first()
        if not company_row:
            raise HTTPException(status_code=403, detail="User is not a company owner")
        return record["company_id"] == company_row["id"]
    
    if current_user.role == "patient":
        # Paciente solo ve sus propios records
        patient_row = db.execute(
            text("SELECT user_id FROM patients WHERE id = :pid"),
            {"pid": record["patient_id"]}
        ).mappings().first()
        if not patient_row:
            return False
        return patient_row["user_id"] == current_user.id
    
    return False

@router.post("/patient/{patient_id}", tags=["Medical Records"])
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
    signature_image_base64: str = Form(default=""),
    signature_licence: str = Form(default=""),
    current_user: User = Depends(require_roles("professional", "admin"))
):
    
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        # Validar que paciente exista
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
            if not signature_image_base64 or not signature_licence:
                raise HTTPException(status_code=400, detail="Admin must provide signature and licence")
            # Para admin, necesita proporcionar professional_id en body
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
            "professional_id": professional_id or _get_professional_id(db, current_user.id),
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
        
        # Agregar firma si se proporciona
        if signature_image_base64 and signature_licence:
            signature_id = str(uuid.uuid4())
            professional_id_for_sig = professional_id or _get_professional_id(db, current_user.id)
            
            db.execute(text("""
                INSERT INTO medical_record_signature
                (id, record_id, signed_by_professional_id, signer_role, signature_image_path, 
                 signature_image_mime, signature_date, licence, created_at, updated_at)
                VALUES 
                (:id, :record_id, :professional_id, :role, :image_path, :mime, :date, :licence, :created, :updated)
            """), {
                "id": signature_id,
                "record_id": record_id,
                "professional_id": professional_id_for_sig,
                "role": current_user.role,
                "image_path": signature_image_base64[:100],  # Almacenar solo inicio
                "mime": "image/png",
                "date": exam_date,
                "licence": signature_licence,
                "created": now,
                "updated": now,
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

@router.get("/patient/{patient_id}", tags=["Medical Records"])
async def get_patient_medical_records(
    patient_id: str,
    current_user: User = Depends(require_active_user)
):
    
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

@router.get("/{record_id}", tags=["Medical Records"])
async def get_medical_record(record_id: str, current_user: User = Depends(require_active_user)):
    
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
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
        
        record = _format_medical_record(row)
        
        # Verificar acceso
        if not _check_access(current_user, record, db):
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        
        return record
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error fetching medical record")
    finally:
        db.close()

@router.patch("/{record_id}", tags=["Medical Records"])
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
    current_user: User = Depends(require_roles("professional", "admin"))
):
    
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
        params = {"rid": record_id, "updated_at": now}
        
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

@router.patch("/{record_id}/signature", tags=["Medical Records"])
async def update_signature(
    record_id: str,
    signature_image_base64: str = Form(...),
    signature_licence: str = Form(...),
    current_user: User = Depends(require_roles("professional", "admin"))
):
    
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        # Validar record existe
        record = db.execute(
            text("SELECT id, exam_date FROM medical_records WHERE id = :rid"),
            {"rid": record_id}
        ).mappings().first()
        
        if not record:
            raise HTTPException(status_code=404, detail="Medical record not found")
        
        # Obtener professional_id
        if current_user.role == "professional":
            professional_id = _get_professional_id(db, current_user.id)
        else:
            raise HTTPException(status_code=400, detail="Only professionals can sign")
        
        # Borrar firma anterior
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
            "image_path": signature_image_base64[:100],
            "mime": "image/png",
            "date": record["exam_date"],
            "licence": signature_licence,
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

@router.patch("/{record_id}/clinical-exam", tags=["Medical Records"])
async def update_clinical_exam(
    record_id: str,
    height_cm: float = Form(default=None),
    weight_kg: float = Form(default=None),
    spo2_percent: float = Form(default=None),
    bmi: float = Form(default=None),
    blood_pressure_min: str = Form(default=None),
    blood_pressure_max: str = Form(default=None),
    current_user: User = Depends(require_roles("professional", "admin"))
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
        
        # Obtener o crear examen clínico
        exam = db.execute(
            text("SELECT id FROM medical_record_clinical_exam WHERE record_id = :rid"),
            {"rid": record_id}
        ).mappings().first()
        
        if exam:
            # Actualizar existente
            updates = []
            params = {"record_id": record_id}
            
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

@router.delete("/{record_id}", tags=["Medical Records"])
async def delete_medical_record(
    record_id: str,
    current_user: User = Depends(require_roles("admin"))
):
    
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
        
        # Eliminar datos relacionados primero
        db.execute(text("DELETE FROM medical_record_signature WHERE record_id = :rid"), {"rid": record_id})
        db.execute(text("DELETE FROM medical_record_clinical_exam WHERE record_id = :rid"), {"rid": record_id})
        db.execute(text("DELETE FROM medical_record_exams_cardiovascular WHERE record_id = :rid"), {"rid": record_id})
        db.execute(text("DELETE FROM medical_record_exams_dental WHERE record_id = :rid"), {"rid": record_id})
        db.execute(text("DELETE FROM medical_record_exams_digestive_abdominal WHERE record_id = :rid"), {"rid": record_id})
        db.execute(text("DELETE FROM medical_record_exams_genitourinario_mens WHERE record_id = :rid"), {"rid": record_id})
        db.execute(text("DELETE FROM medical_record_exams_genitourinario_womens WHERE record_id = :rid"), {"rid": record_id})
        db.execute(text("DELETE FROM medical_record_exams_head_or_neck WHERE record_id = :rid"), {"rid": record_id})
        db.execute(text("DELETE FROM medical_record_exams_neurology WHERE record_id = :rid"), {"rid": record_id})
        db.execute(text("DELETE FROM medical_record_exams_oftalmology WHERE record_id = :rid"), {"rid": record_id})
        db.execute(text("DELETE FROM medical_record_exams_orl WHERE record_id = :rid"), {"rid": record_id})
        db.execute(text("DELETE FROM medical_record_exams_osteoarticular WHERE record_id = :rid"), {"rid": record_id})
        db.execute(text("DELETE FROM medical_record_exams_psychiatric WHERE record_id = :rid"), {"rid": record_id})
        db.execute(text("DELETE FROM medical_record_exams_skin WHERE record_id = :rid"), {"rid": record_id})
        db.execute(text("DELETE FROM medical_record_exams_thoracic_respiratory WHERE record_id = :rid"), {"rid": record_id})
        db.execute(text("DELETE FROM medical_record_exposures WHERE record_id = :rid"), {"rid": record_id})
        db.execute(text("DELETE FROM medical_record_family_history WHERE record_id = :rid"), {"rid": record_id})
        db.execute(text("DELETE FROM medical_record_habits WHERE record_id = :rid"), {"rid": record_id})
        db.execute(text("DELETE FROM medical_record_immunizations WHERE record_id = :rid"), {"rid": record_id})
        db.execute(text("DELETE FROM medical_record_performed_studies WHERE record_id = :rid"), {"rid": record_id})
        db.execute(text("DELETE FROM medical_record_personal_history WHERE record_id = :rid"), {"rid": record_id})
        db.execute(text("DELETE FROM medical_record_surgeries WHERE record_id = :rid"), {"rid": record_id})
        db.execute(text("DELETE FROM medical_record_symptoms WHERE record_id = :rid"), {"rid": record_id})
        db.execute(text("DELETE FROM medical_record_work_risks WHERE record_id = :rid"), {"rid": record_id})
        db.execute(text("DELETE FROM occupational_history_entries WHERE record_id = :rid"), {"rid": record_id})
        
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
