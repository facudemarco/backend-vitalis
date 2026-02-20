from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from models.user import User, professionals
from auth.authentication import require_roles, require_active_user
from Database.getConnection import getConnectionForLogin
from sqlalchemy import text

router = APIRouter(prefix="/admin/users", tags=["Admin - Users"])

# ==================== HELPERS ====================

def _format_user(row) -> dict:
    """Formatea user sin incluir hashed_password"""
    return {
        "id": row["id"],
        "email": row["email"],
        "first_name": row["first_name"],
        "last_name": row["last_name"],
        "dni": row["dni"],
        "date_of_birth": row["date_of_birth"],
        "phone": row["phone"],
        "role": row["role"],
        "is_active": row["is_active"],
        "created_at": row.get("created_at"),
    }

# ==================== GET USERS ====================

@router.get("/", tags=["Admin - Users"])
async def get_users(current_user: User = Depends(require_roles("admin"))):
    """Listar todos los usuarios (solo admin)"""
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        rows = db.query(User).all()
        users = [_format_user({
            "id": u.id,
            "email": u.email,
            "first_name": u.first_name,
            "last_name": u.last_name,
            "dni": u.dni,
            "date_of_birth": u.date_of_birth,
            "phone": u.phone,
            "role": u.role,
            "is_active": u.is_active,
            "created_at": getattr(u, 'created_at', None),
        }) for u in rows]
        return {"users": users, "total": len(users)}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error fetching users")
    finally:
        db.close()


@router.get("/getProfessionals", tags=["Admin - Users"])
async def get_professionals(current_user: User = Depends(require_roles("admin"))):
    """Obtener profesionales (solo admin)"""
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        # Join User and professionals tables
        rows = db.query(User, professionals).join(professionals, User.id == professionals.user_id).all()
        
        result_list = []
        for u, p in rows:
            result_list.append({
                "professional_id": p.id,
                "user_id": u.id,
                "name": u.first_name,
                "lastname": u.last_name,
                "dni": u.dni,
                "date_of_birth": u.date_of_birth,
                "license_number": p.license_number,
                "profesion": p.profesion,
                "email": u.email,
                "speciality": p.speciality,
                "phone": p.phone,
                "created_at": getattr(u, 'created_at', None),
            })
            
        return {"users": result_list, "total": len(result_list)}
    except Exception as e:
        print(f"Error fetching professionals: {e}")
        raise HTTPException(status_code=500, detail="Error fetching professionals")
    finally:
        db.close()

@router.get("/{user_id}", tags=["Admin - Users"])
async def get_user_by_id(user_id: str, current_user: User = Depends(require_roles("admin"))):
    """Obtener usuario por ID (solo admin)"""
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        return _format_user({
            "id": user.id,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "dni": user.dni,
            "date_of_birth": user.date_of_birth,
            "phone": user.phone,
            "role": user.role,
            "is_active": user.is_active,
            "created_at": getattr(user, 'created_at', None),
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error fetching user")
    finally:
        db.close()

@router.get("/state/{state}", tags=["Admin - Users"])
async def get_users_by_state(state: str, current_user: User = Depends(require_roles("admin"))):
    """Filtrar usuarios por estado (true/false) (solo admin)"""
    if state.lower() not in ("true", "false"):
        raise HTTPException(status_code=400, detail="State must be 'true' or 'false'")
    
    is_active = state.lower() == "true"
    
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        rows = db.query(User).filter(User.is_active == is_active).all()
        users = [_format_user({
            "id": u.id,
            "email": u.email,
            "first_name": u.first_name,
            "last_name": u.last_name,
            "dni": u.dni,
            "date_of_birth": u.date_of_birth,
            "phone": u.phone,
            "role": u.role,
            "is_active": u.is_active,
            "created_at": getattr(u, 'created_at', None),
        }) for u in rows]
        return {"users": users, "total": len(users), "state": state}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error fetching users by state")
    finally:
        db.close()

@router.get("/role/{role}", tags=["Admin - Users"])
async def get_users_by_role(role: str, current_user: User = Depends(require_roles("admin"))):
    """Filtrar usuarios por rol (solo admin)"""
    valid_roles = ["admin", "company", "professional", "patient"]
    if role.lower() not in valid_roles:
        raise HTTPException(status_code=400, detail=f"Role must be one of: {', '.join(valid_roles)}")
    
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        rows = db.query(User).filter(User.role == role.lower()).all()
        users = [_format_user({
            "id": u.id,
            "email": u.email,
            "first_name": u.first_name,
            "last_name": u.last_name,
            "dni": u.dni,
            "date_of_birth": u.date_of_birth,
            "phone": u.phone,
            "role": u.role,
            "is_active": u.is_active,
            "created_at": getattr(u, 'created_at', None),
        }) for u in rows]
        return {"users": users, "total": len(users), "role": role.lower()}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error fetching users by role")
    finally:
        db.close()


    
# ==================== UPDATE EXTENDED PROFILES ====================

from fastapi import Form

@router.put("/admin/{user_id}", tags=["Admin - Users"])
async def update_admin_profile(
    user_id: str,
    first_name: str = Form(...),
    last_name: str = Form(...),
    phone: str = Form(default=""),
    dni: str = Form(default=""),
    date_of_birth: str = Form(default=""),
    current_user: User = Depends(require_roles("admin"))
):
    """Actualiza la informacion del admin en la tabla base users"""
    db = getConnectionForLogin()
    if not db:
        raise HTTPException(status_code=500, detail="Database connection error")
        
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
             
        user.first_name = first_name
        user.last_name = last_name
        user.phone = phone
        user.dni = dni
        user.date_of_birth = date_of_birth
        
        db.commit()
        return {"detail": "Admin profile updated successfully", "user_id": user_id}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Error updating profile: " + str(e))
    finally:
        db.close()

@router.put("/patient/{user_id}", tags=["Admin - Users"])
async def update_patient_profile(
    user_id: str,
    address: str = Form(default=""),
    social_security: str = Form(default=""),
    current_user: User = Depends(require_roles("admin"))
):
    """Actualiza la informacion en la tabla patients"""
    db = getConnectionForLogin()
    if not db:
        raise HTTPException(status_code=500, detail="Database connection error")
        
    try:
        db.execute(text("""
            UPDATE patients
            SET address = :address, social_security = :social_security
            WHERE user_id = :uid
        """), {"address": address, "social_security": social_security, "uid": user_id})
        db.commit()
        return {"detail": "Patient profile updated successfully", "user_id": user_id}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Error updating patient: " + str(e))
    finally:
        db.close()
        
@router.put("/professional/{user_id}", tags=["Admin - Users"])
async def update_professional_profile(
    user_id: str,
    license_number: str = Form(default=""),
    profesion: str = Form(default=""),
    speciality: str = Form(default=""),
    phone: str = Form(default=""),
    current_user: User = Depends(require_roles("admin"))
):
    """Actualiza la informacion en la tabla professionals (incluye profesion)"""
    db = getConnectionForLogin()
    if not db:
        raise HTTPException(status_code=500, detail="Database connection error")
        
    try:
        db.execute(text("""
            UPDATE professionals
            SET license_number = :license_number, profesion = :profesion,
                speciality = :speciality, phone = :phone
            WHERE user_id = :uid
        """), {
            "license_number": license_number,
            "profesion": profesion,
            "speciality": speciality,
            "phone": phone,
            "uid": user_id
        })
        db.commit()
        return {"detail": "Professional profile updated successfully", "user_id": user_id}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Error updating professional: " + str(e))
    finally:
        db.close()

@router.put("/company/{user_id}", tags=["Admin - Users"])
async def update_company_profile(
    user_id: str,
    name: str = Form(default=""),
    responsable_name: str = Form(default=""),
    cuit: str = Form(default=""),
    phone: str = Form(default=""),
    address: str = Form(default=""),
    current_user: User = Depends(require_roles("admin"))
):
    """Actualiza la informacion en la tabla companies usando el owner_user_id"""
    db = getConnectionForLogin()
    if not db:
        raise HTTPException(status_code=500, detail="Database connection error")
        
    try:
        db.execute(text("""
            UPDATE companies
            SET name = :name, responsable_name = :responsable_name, cuit = :cuit,
                phone = :phone, address = :address
            WHERE owner_user_id = :uid
        """), {
            "name": name,
            "responsable_name": responsable_name,
            "cuit": cuit,
            "phone": phone,
            "address": address,
            "uid": user_id
        })
        db.commit()
        return {"detail": "Company profile updated successfully", "user_id": user_id}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Error updating company: " + str(e))
    finally:
        db.close()


# ==================== PATCH USER ====================

@router.patch("/{user_id}", tags=["Admin - Users"])
async def update_user(
    user_id: str,
    role: Optional[str] = None,
    is_active: Optional[bool] = None,
    current_user: User = Depends(require_roles("admin"))
):
    """Cambiar role e is_active de un usuario (solo admin)"""
    if role is None and is_active is None:
        raise HTTPException(status_code=400, detail="Must provide at least 'role' or 'is_active'")
    
    valid_roles = ["admin", "company", "professional", "patient"]
    if role and role.lower() not in valid_roles:
        raise HTTPException(status_code=400, detail=f"Role must be one of: {', '.join(valid_roles)}")
    
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        if role:
            user.role = role.lower()
        if is_active is not None:
            user.is_active = is_active
        
        db.commit()
        db.refresh(user)
        
        return {
            "detail": "User updated successfully",
            "user": _format_user({
                "id": user.id,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "dni": user.dni,
                "date_of_birth": user.date_of_birth,
                "phone": user.phone,
                "role": user.role,
                "is_active": user.is_active,
                "created_at": getattr(user, 'created_at', None),
            })
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Error updating user")
    finally:
        db.close()

# ==================== DELETE USER ====================

@router.delete("/{user_id}", tags=["Admin - Users"])
async def deactivate_user(user_id: str, current_user: User = Depends(require_roles("admin"))):
    """Delete: marca usuario como inactivo (solo admin)"""
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        user.is_active = False
        db.commit()
        
        return {
            "detail": "User deactivated successfully",
            "user_id": user_id
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Error deactivating user: " + str(e))
    finally:
        db.close()

@router.delete("/delete/{user_id}", tags=["Admin - Users"])
async def delete_user(user_id: str, current_user: User = Depends(require_roles("admin"))):
    """Delete: eliminar usuario (solo admin) desvinculando de tablas dependientes"""
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        db.execute(text("SET SESSION foreign_key_checks = 0;"))
        
        db.execute(text("DELETE FROM patients WHERE user_id = :uid"), {"uid": user_id})
        db.execute(text("DELETE FROM professionals WHERE user_id = :uid"), {"uid": user_id})
        db.execute(text("DELETE FROM companies WHERE owner_user_id = :uid"), {"uid": user_id})
        
        db.delete(user)
        db.commit()
        
        return {
            "detail": "User deleted successfully",
            "user_id": user_id
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Error deleting user: " + str(e))
    finally:
        try:
            db.execute(text("SET SESSION foreign_key_checks = 1;"))
            db.commit()
        except:
            pass
        db.close()