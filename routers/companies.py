from fastapi import APIRouter, Depends, HTTPException, status, Form, Query
from models.user import User
from auth.authentication import require_roles, require_active_user
from Database.getConnection import getConnectionForLogin
from sqlalchemy import text
import uuid
from services.data_deletion import (
    company_deletion_roots,
    delete_related_records,
    deletion_confirmation_token,
    remove_related_files,
    summarize_related_records,
)

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
        if current_user.role in ("admin", "professional", "secretary"):
            # Admin/secretary/professional ve todas
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
        elif current_user.role not in ("admin", "company", "secretary"):
            raise HTTPException(status_code=403, detail="Only admin, secretary or company owners can view companies")
        
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
    if current_user.role not in ("admin", "company", "secretary"):
        raise HTTPException(status_code=403, detail="Only admin, secretary or company owners can create employees")
    
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
        
        # Convertir DNI a int para la tabla patients - strip non-digits first
        dni_int = 0
        if dni:
            clean_dni = "".join(filter(str.isdigit, str(dni)))
            if clean_dni:
                dni_int = int(clean_dni)
        
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

# ==================== DELETION PREVIEWS AND ADMIN DELETION ====================

@router.get("/{company_id}/deletion-summary", tags=["Companies"])
async def get_company_deletion_summary(
    company_id: str,
    current_user: User = Depends(require_roles("admin")),
):
    """Vista previa de empleados y datos vinculados que se borrarían."""
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    try:
        company = db.execute(
            text("SELECT id, name FROM companies WHERE id = :id"),
            {"id": company_id},
        ).mappings().first()
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")

        roots, employee_ids, _owner_id = company_deletion_roots(db, company_id)
        employees = db.execute(
            text("SELECT id, first_name, last_name FROM patients WHERE company_id = :company_id ORDER BY last_name, first_name"),
            {"company_id": company_id},
        ).mappings().all()
        return {
            "company_id": company_id,
            "company_name": company["name"],
            "employees": [
                {"id": row["id"], "name": " ".join(part for part in (row["first_name"], row["last_name"]) if part) or "Empleado"}
                for row in employees
            ],
            "employee_count": len(employee_ids),
            "related_data": summarize_related_records(db, roots),
            "confirmation_token": deletion_confirmation_token(db, roots),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Could not prepare deletion summary: " + str(e))
    finally:
        db.close()


@router.delete("/{company_id}", tags=["Companies"])
async def delete_company(
    company_id: str,
    confirmed: bool = Query(False),
    confirmation_token: str = Query(""),
    current_user: User = Depends(require_roles("admin")),
):
    """Elimina empresa, empleados, cuentas y todos sus datos relacionados."""
    if not confirmed or not confirmation_token:
        raise HTTPException(status_code=400, detail="Confirm deletion of the company and all related data")

    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    try:
        roots, employee_ids, owner_user_id = company_deletion_roots(db, company_id)
        if not roots:
            raise HTTPException(status_code=404, detail="Company not found")
        if deletion_confirmation_token(db, roots) != confirmation_token:
            raise HTTPException(status_code=409, detail="Related data changed; retrieve a new deletion summary")

        # Delete users belonging to employees as additional roots. The company FK
        # points to patient rows, while employee accounts are the referenced rows.
        files = delete_related_records(db, roots)
        db.commit()
        remove_related_files(files)
        return {
            "detail": "Company and all related data deleted successfully",
            "company_id": company_id,
            "deleted_employee_count": len(employee_ids),
            "deleted_owner_user_id": owner_user_id,
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Error deleting company and related data: " + str(e))
    finally:
        db.close()


@router.get("/{company_id}/employees/{patient_id}/deletion-summary", tags=["Companies"])
async def get_employee_deletion_summary(
    company_id: str,
    patient_id: str,
    current_user: User = Depends(require_roles("admin")),
):
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    try:
        patient = db.execute(
            text("SELECT id, user_id, first_name, last_name FROM patients WHERE id = :pid AND company_id = :cid"),
            {"pid": patient_id, "cid": company_id},
        ).mappings().first()
        if not patient:
            raise HTTPException(status_code=404, detail="Employee not found")
        roots = [("patients", patient_id)]
        if patient["user_id"]:
            roots.append(("users", str(patient["user_id"])))
        return {
            "patient_id": patient_id,
            "patient_name": " ".join(part for part in (patient["first_name"], patient["last_name"]) if part) or "Empleado",
            "related_data": summarize_related_records(db, roots),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Could not prepare deletion summary: " + str(e))
    finally:
        db.close()


@router.delete("/{company_id}/employees/{patient_id}", tags=["Companies"])
async def delete_employee(
    company_id: str,
    patient_id: str,
    confirmed: bool = Query(False),
    confirmation_token: str = Query(""),
    current_user: User = Depends(require_roles("admin")),
):
    """Eliminación de empleado reservada a administradores y con confirmación."""
    if not confirmed or not confirmation_token:
        raise HTTPException(status_code=400, detail="Confirm deletion of the employee and all related data")

    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    try:
        patient = db.execute(
            text("SELECT id, user_id FROM patients WHERE id = :pid AND company_id = :cid"),
            {"pid": patient_id, "cid": company_id},
        ).mappings().first()
        if not patient:
            raise HTTPException(status_code=404, detail="Employee not found")

        roots = [("patients", patient_id)]
        if patient["user_id"]:
            roots.append(("users", str(patient["user_id"])))
        if deletion_confirmation_token(db, roots) != confirmation_token:
            raise HTTPException(status_code=409, detail="Related data changed; retrieve a new deletion summary")
        files = delete_related_records(db, roots)
        db.commit()
        remove_related_files(files)
        return {"detail": "Employee and all related data deleted successfully", "patient_id": patient_id}
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Error deleting employee and related data: " + str(e))
    finally:
        db.close()
