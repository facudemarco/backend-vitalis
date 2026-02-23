from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from typing import Optional
from models.user import User
from auth.authentication import require_active_user
from Database.getConnection import getConnectionForLogin
from sqlalchemy import text

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
