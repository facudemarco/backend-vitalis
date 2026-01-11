from fastapi import APIRouter, Depends, HTTPException, status, Query
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
        query = text("SELECT id, first_name, last_name, dni, date_of_birth, phone, address, social_security, company_id, user_id FROM patients WHERE 1=1")
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
                query = text(f"SELECT id, first_name, last_name, dni, date_of_birth, phone, address, social_security, company_id, user_id FROM patients WHERE company_id = :company_id")
        
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
            SELECT id, first_name, last_name, dni, date_of_birth, phone, address, social_security, company_id, user_id
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

