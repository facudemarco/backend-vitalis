from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from typing import Optional
from models.user import User
from auth.authentication import require_active_user, require_roles
from Database.getConnection import getConnectionForLogin
from sqlalchemy import text
import os
from pathlib import Path
import shutil

router = APIRouter(prefix="/patients", tags=["Patients"])

# ==================== HELPERS ====================

def _format_patient(row) -> dict:
    """Formatea patient"""
    return {
        "id": row["id"],
        "first_name": row["first_name"],
        "last_name": row["last_name"],
        "dni": row["dni"],
        "date_of_birth": row["date_of_birth"],
        "phone": row["phone"],
        "address": row["address"],
        "social_security": row["social_security"],
        "company_id": row["company_id"],
        "user_id": row["user_id"],
        "study_type": row["study_type"],
    }

# ==================== GET PATIENTS ====================

@router.get("/", tags=["Patients"])
async def get_patients(
    company_id: str = Query(None),
    user_id: str = Query(None),
    dni: str = Query(None),
    current_user: User = Depends(require_active_user)
):
    """Listar pacientes (con filtros según rol)
    
    - Admin: ve todos los pacientes
    - Company owner: ve solo pacientes de su empresa
    - Professional: ve todos, puede filtrar por DNI
    """
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        query = text("SELECT id, first_name, last_name, dni, date_of_birth, phone, address, social_security, company_id, user_id, study_type FROM patients WHERE 1=1")
        params = {}
        
        # Filtrar según rol
        if current_user.role == "admin":
            # Admin ve todo, puede aplicar filtros opcionales
            if company_id:
                query = text(query.text + " AND company_id = :company_id")
                params["company_id"] = company_id
            if user_id:
                query = text(query.text + " AND user_id = :user_id")
                params["user_id"] = user_id
            if dni:
                query = text(query.text + " AND dni LIKE :dni")
                params["dni"] = f"%{dni}%"
        
        elif current_user.role == "company":
            # Company owner solo ve sus empleados
            query = text(query.text + " AND company_id = :company_id")
            params["company_id"] = current_user.id  # Obtener company_id del owner
            
            # Validar que si pasa company_id, sea el suyo
            if company_id and company_id != current_user.id:
                raise HTTPException(status_code=403, detail="You can only view your own company patients")
            
            # Obtener el company_id real del owner
            company_row = db.execute(text("SELECT id FROM companies WHERE owner_user_id = :user_id"), {"user_id": current_user.id}).mappings().first()
            if company_row:
                params["company_id"] = company_row["id"]
                query = text("SELECT id, first_name, last_name, dni, date_of_birth, phone, address, social_security, company_id, user_id, study_type FROM patients WHERE company_id = :company_id")
        
        elif current_user.role == "professional":
            # Professional ve todos, puede filtrar por DNI
            if dni:
                query = text(query.text + " AND dni LIKE :dni")
                params["dni"] = f"%{dni}%"
            if company_id:
                query = text(query.text + " AND company_id = :company_id")
                params["company_id"] = company_id
            if user_id:
                query = text(query.text + " AND user_id = :user_id")
                params["user_id"] = user_id
        
        else:
            raise HTTPException(status_code=403, detail="Only admin, company owners, or professionals can list patients")
        
        rows = db.execute(query, params).mappings().all()
        patients = [_format_patient(row) for row in rows]
        return {"patients": patients, "total": len(patients)}
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail="Error fetching patients")
    finally:
        db.close()

@router.get("/getPatients", tags=["Patients"])
async def getPatients(current_user: User = Depends(require_active_user)):
    """Obtener todos los pacientes"""
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    try:
        rows = db.execute(text("SELECT * FROM patients")).mappings().all()
        return [_format_patient(row) for row in rows]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error fetching patients" + str(e))
    finally:
        db.close()

@router.get("/{patient_id}", tags=["Patients"])
async def get_patient_by_id(patient_id: str, current_user: User = Depends(require_active_user)):
    """Obtener detalles de paciente
    
    - Paciente mismo (si es usuario)
    - Admin
    - Médicos (profesionales)
    - Company owner (si es empleado de su empresa)
    """
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        row = db.execute(text("""
            SELECT id, first_name, last_name, dni, date_of_birth, phone, address, social_security, company_id, user_id, study_type
            FROM patients
            WHERE id = :id
        """), {"id": patient_id}).mappings().first()
        
        if not row:
            raise HTTPException(status_code=404, detail="Patient not found")
        
        # Validar acceso según rol
        if current_user.role == "admin":
            # Admin ve todo
            pass
        elif current_user.role == "professional":
            # Profesional ve a cualquier paciente
            pass
        elif current_user.role == "patient":
            # Paciente solo ve sus datos
            if row["user_id"] != current_user.id:
                raise HTTPException(status_code=403, detail="You can only view your own patient data")
        elif current_user.role == "company":
            # Company owner ve pacientes de su empresa
            company_row = db.execute(text("SELECT id FROM companies WHERE owner_user_id = :user_id"), {"user_id": current_user.id}).mappings().first()
            if not company_row or row["company_id"] != company_row["id"]:
                raise HTTPException(status_code=403, detail="You can only view patients from your own company")
        else:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        
        return _format_patient(row)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error fetching patient")
    finally:
        db.close()


# ==================== PUT PATIENT ====================

@router.put("/{patient_id}", tags=["Patients"])
async def update_patient(
    patient_id: str,
    first_name: Optional[str] = Body(None),
    last_name: Optional[str] = Body(None),
    dni: Optional[str] = Body(None),
    date_of_birth: Optional[str] = Body(None),
    phone: Optional[str] = Body(None),
    address: Optional[str] = Body(None),
    social_security: Optional[str] = Body(None),
    company_id: Optional[str] = Body(None),
    study_type: Optional[str] = Body(None),
    current_user: User = Depends(require_active_user)
):
    """Actualizar datos de un paciente (incluye study_type).

    - Admin: puede actualizar cualquier paciente
    - Paciente mismo: solo sus propios datos
    - Professional: puede editar cualquier paciente
    - Company owner: solo pacientes de su empresa
    """
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")

    try:
        row = db.execute(
            text("SELECT id, user_id, company_id FROM patients WHERE id = :id"),
            {"id": patient_id}
        ).mappings().first()

        if not row:
            raise HTTPException(status_code=404, detail="Patient not found")

        # Control de acceso
        if current_user.role == "admin":
            pass
        elif current_user.role == "patient":
            if row["user_id"] != current_user.id:
                raise HTTPException(status_code=403, detail="You can only edit your own patient data")
        elif current_user.role == "professional":
            pass
        elif current_user.role == "company":
            company_row = db.execute(
                text("SELECT id FROM companies WHERE owner_user_id = :user_id"),
                {"user_id": current_user.id}
            ).mappings().first()
            if not company_row or row["company_id"] != company_row["id"]:
                raise HTTPException(status_code=403, detail="You can only edit patients from your own company")
        else:
            raise HTTPException(status_code=403, detail="Insufficient permissions")

        # Construir SET dinámico solo con campos enviados
        fields = {
            "first_name": first_name,
            "last_name": last_name,
            "dni": dni,
            "date_of_birth": date_of_birth,
            "phone": phone,
            "address": address,
            "social_security": social_security,
            "company_id": company_id,
            "study_type": study_type,
        }
        updates = {k: v for k, v in fields.items() if v is not None}

        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")

        set_clause = ", ".join([f"{k} = :{k}" for k in updates])
        updates["patient_id"] = patient_id

        db.execute(
            text(f"UPDATE patients SET {set_clause} WHERE id = :patient_id"),
            updates
        )
        db.commit()

        updated = db.execute(
            text("SELECT id, first_name, last_name, dni, date_of_birth, phone, address, social_security, company_id, user_id, study_type FROM patients WHERE id = :id"),
            {"id": patient_id}
        ).mappings().first()

        return _format_patient(updated)

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Error updating patient: " + str(e))
    finally:
        db.close()


# ==================== DELETE PATIENT ====================

# Paths mirrored from medical_records.py and studies.py
_SIGNATURES_DIR_ENV = os.getenv("SIGNATURES_DIR")
if _SIGNATURES_DIR_ENV:
    _SIGNATURES_DIR = Path(_SIGNATURES_DIR_ENV)
elif os.name == "posix":
    _SIGNATURES_DIR = Path("/home/iweb/vitalis/data/signatures/")
else:
    _BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    _SIGNATURES_DIR = Path(os.path.join(_BASE_DIR, "signatures"))

_DATA_IMAGES_DIR_ENV = os.getenv("DATA_IMAGES_DIR")
if _DATA_IMAGES_DIR_ENV:
    _DATA_IMAGES_DIR = Path(_DATA_IMAGES_DIR_ENV)
else:
    _BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    _DATA_IMAGES_DIR = Path(os.path.join(_BASE_DIR, "data_images"))

_STUDIES_DIR = os.getenv("STUDIES_DIR", "/home/iweb/vitalis/data/studies/")
if os.name != "posix" and not os.getenv("STUDIES_DIR"):
    _BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    _STUDIES_DIR = os.path.join(_BASE_DIR, "studies")


def _delete_file_from_url(url: str, directory) -> None:
    """Elimina un archivo físico dado su URL y directorio base."""
    if not url:
        return
    try:
        filename = url.split("/")[-1]
        file_path = Path(directory) / filename
        if file_path.exists():
            os.remove(file_path)
    except Exception as e:
        print(f"Warning: could not delete file {url}: {e}")


@router.delete("/{patient_id}", tags=["Patients"])
async def delete_patient(
    patient_id: str,
    current_user: User = Depends(require_roles("admin"))
):
    """Eliminar un paciente y TODOS sus datos relacionados:
    - medical_record (y todas sus sub-tablas + archivos físicos)
    - studies (y study_files + archivos físicos)
    - patients
    - users (el usuario vinculado)
    """
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")

    try:
        # 1. Verificar que el paciente existe y obtener su user_id
        patient_row = db.execute(
            text("SELECT id, user_id FROM patients WHERE id = :pid"),
            {"pid": patient_id}
        ).mappings().first()

        if not patient_row:
            raise HTTPException(status_code=404, detail="Patient not found")

        user_id = patient_row["user_id"]

        # ----------------------------------------------------------------
        # 2. Eliminar todos los medical_records del paciente
        # ----------------------------------------------------------------
        medical_records = db.execute(
            text("SELECT id FROM medical_record WHERE patient_id = :pid"),
            {"pid": patient_id}
        ).mappings().all()

        mr_sub_tables = [
            "medical_record_bucodental_exam", "medical_record_cardiovascular_exam",
            "medical_record_clinical_exam", "medical_record_derivations",
            "medical_record_digestive_exam", "medical_record_evaluation_type",
            "medical_record_family_history", "medical_record_genitourinario_exam",
            "medical_record_habits", "medical_record_head_exam",
            "medical_record_immunizations", "medical_record_laboral_contacts",
            "medical_record_laboral_exam", "medical_record_laboral_history",
            "medical_record_neuro_clinical_exam", "medical_record_oftalmologico_exam",
            "medical_record_orl_exam", "medical_record_osteoarticular_exam",
            "medical_record_personal_history", "medical_record_previous_problems",
            "medical_record_psychiatric_clinical_exam", "medical_record_recomendations",
            "medical_record_respiratorio_exam", "medical_record_skin_exam",
            "medical_record_studies", "medical_record_surgerys",
            "medical_record_laboral_signatures", "medical_record_signatures",
            "medical_record_cuestionario_riesgos", "medical_record_ddjj",
            "medical_record_neuro_medical_exam",
        ]

        for mr in medical_records:
            rid = str(mr["id"])

            # A. Recolectar y borrar archivos físicos de firmas
            for sig in db.execute(
                text("SELECT url FROM medical_record_signatures WHERE medical_record_id = :rid"),
                {"rid": rid}
            ).mappings().all():
                _delete_file_from_url(sig["url"], _SIGNATURES_DIR)

            for l_sig in db.execute(
                text("SELECT url FROM medical_record_laboral_signatures WHERE medical_record_id = :rid"),
                {"rid": rid}
            ).mappings().all():
                _delete_file_from_url(l_sig["url"], _SIGNATURES_DIR)

            # B. Recolectar y borrar archivos físicos de data images
            for dr in db.execute(
                text("SELECT id FROM medical_record_data WHERE medical_record_id = :rid"),
                {"rid": rid}
            ).mappings().all():
                for img in db.execute(
                    text("SELECT url FROM medical_record_data_img WHERE medical_record_data_id = :did"),
                    {"did": dr["id"]}
                ).mappings().all():
                    _delete_file_from_url(img["url"], _DATA_IMAGES_DIR)
                db.execute(
                    text("DELETE FROM medical_record_data_img WHERE medical_record_data_id = :did"),
                    {"did": dr["id"]}
                )

            # C. Borrar medical_record_data
            db.execute(text("DELETE FROM medical_record_data WHERE medical_record_id = :rid"), {"rid": rid})

            # D. Borrar todas las sub-tablas restantes
            for table in mr_sub_tables:
                db.execute(text(f"DELETE FROM {table} WHERE medical_record_id = :rid"), {"rid": rid})

            # E. Borrar registro padre medical_record
            db.execute(text("DELETE FROM medical_record WHERE id = :rid"), {"rid": rid})

        # ----------------------------------------------------------------
        # 3. Eliminar todos los studies del paciente
        # ----------------------------------------------------------------
        studies = db.execute(
            text("SELECT id FROM studies WHERE patient_id = :pid"),
            {"pid": patient_id}
        ).mappings().all()

        for study in studies:
            sid = str(study["id"])

            # Borrar archivos físicos
            for f in db.execute(
                text("SELECT file_path FROM study_files WHERE study_id = :sid"),
                {"sid": sid}
            ).mappings().all():
                try:
                    fname = os.path.basename(f["file_path"])
                    local_path = os.path.join(_STUDIES_DIR, fname)
                    if os.path.exists(local_path):
                        os.remove(local_path)
                except Exception as e:
                    print(f"Warning: could not delete study file: {e}")

            db.execute(text("DELETE FROM study_files WHERE study_id = :sid"), {"sid": sid})
            db.execute(text("DELETE FROM studies WHERE id = :sid"), {"sid": sid})

        # ----------------------------------------------------------------
        # 4. Eliminar el paciente
        # ----------------------------------------------------------------
        db.execute(text("DELETE FROM patients WHERE id = :pid"), {"pid": patient_id})

        # ----------------------------------------------------------------
        # 5. Eliminar el usuario vinculado (si existe)
        # ----------------------------------------------------------------
        if user_id:
            db.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": user_id})

        db.commit()
        return {"detail": "Patient and all related data deleted successfully", "patient_id": patient_id}

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Error deleting patient: " + str(e))
    finally:
        db.close()

