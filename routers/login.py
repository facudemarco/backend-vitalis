from Database.users import hash_password
from datetime import datetime
from queue import PriorityQueue
from fastapi import FastAPI, Depends, HTTPException, APIRouter, Response, Cookie, Request, Form
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import JSONResponse
from auth.authentication import oauth2_scheme, get_current_user, create_access_token, verify_token, require_roles, require_active_user
from models.user import User, UserCreate, UserUpdate, UserSchema
from Database.getConnection import getConnectionForLogin, getConnection
from Database.users import get_user_by_email, authenticate_user, resolve_profile_ids, build_token_payload
from sqlalchemy import JSON, text
import uuid
import os
from typing import Annotated, Optional, Union
from fastapi.middleware.cors import CORSMiddleware

router = APIRouter()

# Login

@router.post("/login", tags=["login"])
async def login(response: Response, email: str = Form(...), password: str = Form(...)):
    user = authenticate_user(email, password)
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect email or password")

    profile = resolve_profile_ids(str(user.id), str(user.role))
    token_payload = build_token_payload(user, profile)
    access_token = create_access_token(data=token_payload)

    response.set_cookie(
        key="Authorization",
        value=f"Bearer {access_token}",
        httponly=True,
        secure=True,       
        samesite="none",    
        max_age=60 * 60 * 24 * 7,   
        path="/",
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user,
        "profile": profile,
    }
    
@router.post("/logout", tags=["login"])
async def logout(response: Response):
    response.delete_cookie(key="Authorization", path="/")
    return {"detail": "Logged out successfully"}

@router.get("/me", tags=["login"])
async def read_current_user(current_user: UserSchema = Depends(require_active_user)):
    profile = resolve_profile_ids(str(current_user.id), str(current_user.role))
    return {
        "user": current_user,
        "profile": profile,
    }
    
@router.get("/verify-token", tags=["login"])
async def verify_current_token(request: Request):
    token = request.cookies.get("Authorization")
    
    if not token:
        return {"valid": False, "detail": "No token in cookies"}
    
    if token.startswith("Bearer "):
        token = token[len("Bearer "):]
    
    try:
        payload = verify_token(token)
        return {"valid": True, "payload": payload}
    except HTTPException:
        return {"valid": False, "detail": "Invalid token"}
    
# Register
@router.post("/auth/register/patient", tags=["Register"])
async def register_patient(
    email: str = Form(...), 
    password: str = Form(...), 
    first_name: str = Form(default=""),
    last_name: str = Form(default=""),
    dni: str = Form(default=""),
    date_of_birth: str = Form(default=""),
    phone: str = Form(default="")
):
    existing_user = get_user_by_email(email)
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_password = hash_password(password)
    user_id = str(uuid.uuid4())
    new_user = User(
        id=user_id,
        email=email,
        hashed_password=hashed_password,
        first_name=first_name,
        last_name=last_name,
        dni=dni,
        date_of_birth=date_of_birth,
        phone=phone,
        role="patient",
        is_active=True,
    )

    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    try:
        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        # Create patient profile
        patient_id = str(uuid.uuid4())
        
        # Handle DNI conversion (str to int safely)
        dni_int = 0
        if dni and dni.isdigit():
            dni_int = int(dni)

        db.execute(
            text("""
                INSERT INTO patients (id, user_id, first_name, last_name, dni, date_of_birth, phone, address, social_security, company_id)
                VALUES (:id, :user_id, :first_name, :last_name, :dni, :date_of_birth, :phone, :address, :social_security, :company_id)
            """),
            {
                "id": patient_id,
                "user_id": new_user.id,
                "first_name": first_name,
                "last_name": last_name,
                "dni": dni_int,
                "date_of_birth": date_of_birth,
                "phone": phone,
                "address": "",
                "social_security": "",
                "company_id": None
            }
        )
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Error creating user")
    finally:
        db.close()

    return {"detail": "Patient registered successfully", "user_id": user_id, "patient_id": patient_id}

@router.post("/auth/register/company", tags=["Register"])
async def register_company(
    email: str = Form(...), 
    password: str = Form(...),
    company_name: str = Form(...),
    responsable_name: str = Form(...),
    cuit: str = Form(...),
    company_phone: str = Form(default=""),
    company_address: str = Form(default=""),
    first_name: str = Form(default=""),
    last_name: str = Form(default=""),
    phone: str = Form(default="")
):

    existing_user = get_user_by_email(email)
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_password = hash_password(password)
    user_id = str(uuid.uuid4())
    company_id = str(uuid.uuid4())
    
    new_user = User(
        id=user_id,
        email=email,
        hashed_password=hashed_password,
        first_name=first_name,
        last_name=last_name,
        phone=phone,
        dni="",
        date_of_birth="",
        role="company",
        is_active=True,
    )

    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        db.add(new_user)
        db.flush()
        
        # Crear registro en tabla companies
        db.execute(
            text("""
                INSERT INTO companies (id, name, responsable_name, cuit, email, phone, address, owner_user_id)
                VALUES (:id, :name, :responsable, :cuit, :email, :phone, :address, :owner_id)
            """),
            {
                "id": company_id,
                "name": company_name,
                "responsable": responsable_name,
                "cuit": cuit,
                "email": email,
                "phone": company_phone,
                "address": company_address,
                "owner_id": user_id,
            }
        )
        
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Error creating company" + str(e))
    finally:
        db.close()

    return {"detail": "Company registered successfully", "user_id": user_id, "company_id": company_id}

@router.post("/auth/register/professional", tags=["Register"])
async def register_professional(
    email: str = Form(...),
    password: str = Form(...),
    license_number: str = Form(...),
    speciality: str = Form(...),
    first_name: str = Form(default=""),
    last_name: str = Form(default=""),
    phone: str = Form(default="")
):
    """Registra un nuevo profesional"""
    existing_user = get_user_by_email(email)
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_password = hash_password(password)
    user_id = str(uuid.uuid4())
    professional_id = str(uuid.uuid4())
    
    new_user = User(
        id=user_id,
        email=email,
        hashed_password=hashed_password,
        first_name=first_name,
        last_name=last_name,
        phone=phone,
        dni="",
        date_of_birth="",
        role="professional",
        is_active=True,
    )

    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        db.add(new_user)
        db.flush()
        
        # Crear registro en tabla professionals
        db.execute(
            text("""
                INSERT INTO professionals (id, user_id, license_number, speciality, phone)
                VALUES (:id, :user_id, :license, :speciality, :phone)
            """),
            {
                "id": professional_id,
                "user_id": user_id,
                "license": license_number,
                "speciality": speciality,
                "phone": phone,
            }
        )
        
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Error creating professional")
    finally:
        db.close()

    return {"detail": "Professional registered successfully", "user_id": user_id, "professional_id": professional_id}

@router.post("/auth/register/admin", tags=["Register"])
async def register_admin(
    email: str = Form(...),
    password: str = Form(...),
    first_name: str = Form(default=""),
    last_name: str = Form(default="")
):
    existing_user = get_user_by_email(email)
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_password = hash_password(password)
    user_id = str(uuid.uuid4())

    new_user = User(
        id=user_id,
        email=email,
        hashed_password=hashed_password,
        first_name=first_name,
        last_name=last_name,
        dni="",
        date_of_birth="",
        phone="",
        role="admin",
        is_active=True,
    )

    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    try:
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Error creating admin, " + str(e))
    finally:
        db.close()

    return {"detail": "Admin registered successfully", "user_id": user_id}

@router.post("/change-password", tags=["Register"])
async def change_password(current_user: UserSchema = Depends(require_active_user), old_password: str = Form(...), new_password: str = Form(...)):
    user = authenticate_user(current_user.email, old_password)
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect old password")

    new_hashed_password = hash_password(new_password)

    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    try:
        user_in_db = db.query(User).filter(User.id == current_user.id).first()
        if not user_in_db:
            raise HTTPException(status_code=404, detail="User not found")
        user_in_db.hashed_password = new_hashed_password
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Error changing password")
    finally:
        db.close()

    return {"detail": "Password changed successfully"}

