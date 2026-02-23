from fastapi import APIRouter, Depends, HTTPException, status, Form
from models.user import User
from auth.authentication import require_roles, require_active_user
from Database.getConnection import getConnectionForLogin
from sqlalchemy import text
import uuid

router = APIRouter(prefix="/companies", tags=["Companies"])

# ==================== HELPERS ====================

def _format_company(row) -> dict:
    """Formatea company"""
    return {
        "id": row["id"],
        "name": row["name"],
        "responsable_name": row["responsable_name"],
        "cuit": row["cuit"],
        "email": row["email"],
        "phone": row["phone"],
        "address": row["address"],
        "owner_user_id": row["owner_user_id"],
    }

# ==================== GET COMPANIES ====================

@router.get("/", tags=["Companies"])
async def get_companies(current_user: User = Depends(require_active_user)):
    """Listar empresas (admin ve todas, owners ven solo la suya)"""
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        if current_user.role == "admin" or current_user.role == "professional":
            # Admin ve todas
            rows = db.execute(text("""
                SELECT id, name, responsable_name, cuit, email, phone, address, owner_user_id
                FROM companies
            """)).mappings().all()
        elif current_user.role == "company":
            # Owner ve solo su empresa
            rows = db.execute(text("""
                SELECT id, name, responsable_name, cuit, email, phone, address, owner_user_id
                FROM companies
                WHERE owner_user_id = :user_id
            """), {"user_id": current_user.id}).mappings().all()
        else:
            raise HTTPException(status_code=403, detail="Only admin or company owners can list companies")
        
        companies = [_format_company(row) for row in rows]
        return {"companies": companies, "total": len(companies)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error fetching companies" + str(e))
    finally:
        db.close()

@router.get("/{company_id}", tags=["Companies"])
async def get_company_by_id(company_id: str, current_user: User = Depends(require_active_user)):
    """Obtener detalles de empresa (admin y owner)"""
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        row = db.execute(text("""
            SELECT id, name, responsable_name, cuit, email, phone, address, owner_user_id
            FROM companies
            WHERE id = :id
        """), {"id": company_id}).mappings().first()
        
        if not row:
            raise HTTPException(status_code=404, detail="Company not found")
        
        # Validar acceso
        if current_user.role == "company" and row["owner_user_id"] != current_user.id:
            raise HTTPException(status_code=403, detail="You can only view your own company")
        elif current_user.role not in ("admin", "company"):
            raise HTTPException(status_code=403, detail="Only admin or company owners can view companies")
        
        return _format_company(row)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error fetching company")
    finally:
        db.close()

# ==================== CREATE EMPLOYEE (PATIENT) ====================

@router.post("/{company_id}/employees", tags=["Companies"])
async def create_employee(
    company_id: str,
    first_name: str = Form(default=""),
    last_name: str = Form(default=""),
    dni: str = Form(default=""),
    date_of_birth: str = Form(default=""),
    phone: str = Form(default=""),
    address: str = Form(default=""),
    social_security: str = Form(default=""),
    study_type: str = Form(default=""),
    current_user: User = Depends(require_active_user)
):
    """
    Crear empleado:
    1) Crea el User en la tabla `users` con rol 'patient' (usando email y password).
    2) Crea el registro en `patients` vinculado con el user_id recién creado.
    Requiere rol admin o company owner.
    """
    
    # Validar que sea admin o owner
    if current_user.role not in ("admin", "company"):
        raise HTTPException(status_code=403, detail="Only admin or company owners can create employees")
    
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        # Validar que la empresa exista
        company = db.execute(text("""
            SELECT id, owner_user_id FROM companies WHERE id = :id
        """), {"id": company_id}).mappings().first()
        
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")
        
        # Si es company, validar que sea owner
        if current_user.role == "company" and company["owner_user_id"] != current_user.id:
            raise HTTPException(status_code=403, detail="You can only create employees for your own company")
        
        user_id = str(uuid.uuid4())
        db.execute(text("""
            INSERT INTO users (id, first_name, last_name, dni, date_of_birth, phone, role, is_active)
            VALUES (:id, :first_name, :last_name, :dni, :date_of_birth, :phone, 'patient', 1)
        """), {
            "id": user_id,  
            "first_name": first_name,
            "last_name": last_name,
            "dni": dni, 
            "date_of_birth": date_of_birth,
            "phone": phone,
        })
        
        # 2) Crear el registro en patients vinculado al user_id recién creado
        patient_id = str(uuid.uuid4())
        
        # Convertir DNI a int para la tabla patients
        dni_int = 0
        if dni and dni.isdigit():
            dni_int = int(dni)
        
        db.execute(text("""
            INSERT INTO patients (id, first_name, last_name, dni, date_of_birth, phone, address, social_security, company_id, user_id, study_type)
            VALUES (:id, :first_name, :last_name, :dni, :date_of_birth, :phone, :address, :social_security, :company_id, :user_id, :study_type)
        """), {
            "id": patient_id,
            "first_name": first_name,
            "last_name": last_name,
            "dni": dni_int,
            "date_of_birth": date_of_birth,
            "phone": phone,
            "address": address,
            "social_security": social_security,
            "company_id": company_id,
            "user_id": user_id,
            "study_type": study_type,
        })
        db.commit()
        
        return {
            "detail": "Employee created successfully",
            "user_id": user_id,
            "patient_id": patient_id,
            "company_id": company_id,
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Error creating employee: " + str(e))
    finally:
        db.close()

# ==================== DELETE EMPLOYEE (PATIENT) ====================

@router.delete("/{company_id}/employees/{patient_id}", tags=["Companies"])
async def delete_employee(
    company_id: str,
    patient_id: str,
    current_user: User = Depends(require_active_user)
):
    """Eliminar paciente (employee) (admin y company owner)"""
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        company = db.execute(text("""
            SELECT id, owner_user_id FROM companies WHERE id = :id
        """), {"id": company_id}).mappings().first()
        
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")
        
        if current_user.role == "company" and company["owner_user_id"] != current_user.id:
            raise HTTPException(status_code=403, detail="You can only delete employees for your own company")
        
        patient_row = db.execute(
            text("SELECT user_id FROM patients WHERE id = :id"),
            {"id": patient_id}
        ).mappings().first()

        if not patient_row:
            raise HTTPException(status_code=404, detail="Employee not found")

        linked_user_id = patient_row["user_id"]

        medical_records = db.execute(
            text("SELECT id FROM medical_record WHERE patient_id = :pid"),
            {"pid": patient_id}
        ).mappings().all()

        for mr in medical_records:
            mr_id = mr["id"]
            study_ids = db.execute(
                text("SELECT id FROM studies WHERE medical_record_id = :mrid"),
                {"mrid": mr_id}
            ).mappings().all()
            for s in study_ids:
                db.execute(text("DELETE FROM study_files WHERE study_id = :sid"), {"sid": s["id"]})
            db.execute(text("DELETE FROM studies WHERE medical_record_id = :mrid"), {"mrid": mr_id})
            db.execute(text("DELETE FROM medical_record WHERE id = :mrid"), {"mrid": mr_id})

        db.execute(text("DELETE FROM patients WHERE id = :id"), {"id": patient_id})

        if linked_user_id:
            db.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": linked_user_id})

        db.commit()
        
        return {
            "detail": "Employee deleted successfully",
            "patient_id": patient_id,
            "company_id": company_id,
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Error deleting employee")
    finally:
        db.close()
