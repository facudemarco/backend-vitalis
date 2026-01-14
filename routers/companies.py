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
        if current_user.role == "admin":
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
    current_user: User = Depends(require_active_user)
):
    """Crear paciente (employee) sin User (admin y company owner)"""
    
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
        
        # Crear paciente
        patient_id = str(uuid.uuid4())
        db.execute(text("""
            INSERT INTO patients (id, first_name, last_name, dni, date_of_birth, phone, address, social_security, company_id, user_id)
            VALUES (:id, :first_name, :last_name, :dni, :date_of_birth, :phone, :address, :social_security, :company_id, NULL)
        """), {
            "id": patient_id,
            "first_name": first_name,
            "last_name": last_name,
            "dni": dni,
            "date_of_birth": date_of_birth,
            "phone": phone,
            "address": address,
            "social_security": social_security,
            "company_id": company_id,
        })
        db.commit()
        
        return {
            "detail": "Employee created successfully",
            "patient_id": patient_id,
            "company_id": company_id,
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Error creating employee")
    finally:
        db.close()
