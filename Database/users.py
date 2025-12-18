import bcrypt
from typing import Optional
from models.user import User
from Database.getConnection import getConnectionForLogin
from sqlalchemy.orm import Session
from sqlalchemy import and_, text
import uuid
from bcrypt import hashpw, gensalt
from fastapi import HTTPException

def get_user_by_email(email: str) -> Optional[User]:
    db = getConnectionForLogin()
    if db is None:
        return None
    
    try:
        user = db.query(User).filter(User.email == email).first()
        return user
    except Exception as e:
        print(f"Error getting user: {e}")
        return None
    finally:
        db.close()

def get_user_by_email_and_password(email: str, password: str):
    user = get_user_by_email(email)
    if user is not None and verify_password(password, str(user.hashed_password)):
        return user
    return None

def get_user_client_by_email(email: str) -> Optional[User]:
    db = getConnectionForLogin()
    if db is None:
        return None
    
    try:
        user_client = db.query(User).filter(User.email == email).first()
        return user_client
    except Exception as e:
        print(f"Error getting user client: {e}")
        return None
    finally:
        db.close()

def verify_user_client(email: str, password: str) -> bool:
    db = getConnectionForLogin()
    if db is None:
        return False
    
    try:
        user_client = db.query(User).filter(User.email == email).first()
        if user_client and verify_password(password, str(user_client.hashed_password)):
            return True
        return False
    except Exception as e:
        print(f"Error verifying user client: {e}")
        return False
    finally:
        db.close()

def verify_user_credentials(email: str, password: str) -> bool:
    """
    Verifica las credenciales del usuario y devuelve True si son válidas
    """
    user = get_user_by_email(email)
    if user is not None and verify_password(password, str(user.hashed_password)):
        return True
    return False

def create_user(email: str, password: str) -> bool:
    db = getConnectionForLogin()
    generated_id = str(uuid.uuid4())
    if db is None:
        return False
    
    try:
        # Verificar si el usuario ya existe
        existing_user = db.query(User).filter(User.email == email).first()
        if existing_user:
            return False
        
        # Crear nuevo usuario
        new_user = User(id=generated_id, email=email, hashed_password=hash_password(password))
        db.add(new_user)
        db.commit()
        return True
    except Exception as e:
        print(f"Error creating user: {e}")
        db.rollback()
        return False
    finally:
        db.close()

def get_user_by_id(id: str) -> Optional[User]:
    db = getConnectionForLogin()
    if db is None:
        return None
    
    try:
        user = db.query(User).filter(User.id == id).first()
        return user
    except Exception as e:
        print(f"Error getting user: {e}")
        return None
    finally:    
        db.close()

def delete_user(id: str):
    db = getConnectionForLogin()
    if db is None:
        return False
    
    try:
        user = db.query(User).filter(User.id == id).first()
        if not user:
            return False
        
        # Eliminar usuario
        db.delete(user)
        db.commit()
        return True
    except Exception as e:
        print(f"Error deleting user: {e}")
        db.rollback()
        return False
    finally:
        db.close()

def update_user(id: str, username: str, password: str, rol: str, local: str) -> bool:
    db = getConnectionForLogin()
    if db is None:
        return False
    try:
        user = db.query(User).filter(User.id == id).first()
        if not user:
            return False
        user.username = username  # type: ignore
        user.password = password  # type: ignore
        user.rol = rol            # type: ignore
        user.local = local        # type: ignore
        db.commit()
        return True
    except Exception as e:
        print(f"Error updating user: {e}")
        db.rollback()
        return False
    finally:
        db.close()
        
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))

def authenticate_user(email: str, password: str) -> Optional[User]:
    user = get_user_by_email(email) 
    if not user:
        return None

    if not bool(user.is_active):
        raise HTTPException(status_code=403, detail="user is inactive")

    if not verify_password(password, str(user.hashed_password)):
        return None

    return user

def resolve_profile_ids(user_id: str, role: str) -> dict:
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="DB connection error")

    try:
        profile = {
            "company_id": None,
            "patient_id": None,
            "professional_id": None,
        }

        if role == "professional":
            row = db.execute(
                text("SELECT id FROM professionals WHERE user_id = :uid LIMIT 1"),
                {"uid": user_id},
            ).mappings().first()
            if not row:
                raise HTTPException(status_code=400, detail="Professional profile missing")
            profile["professional_id"] = row["id"]

        elif role == "patient":
            row = db.execute(
                text("SELECT id, company_id FROM patients WHERE user_id = :uid LIMIT 1"),
                {"uid": user_id},
            ).mappings().first()
            if not row:
                raise HTTPException(status_code=400, detail="Patient profile missing")
            profile["patient_id"] = row["id"]
            profile["company_id"] = row.get("company_id")

        elif role == "company":
            row = db.execute(
                text("SELECT id FROM companies WHERE owner_user_id = :uid LIMIT 1"),
                {"uid": user_id},
            ).mappings().first()
            if not row:
                raise HTTPException(status_code=400, detail="Company profile missing")
            profile["company_id"] = row["id"]

        elif role == "admin":
            pass
        else:
            raise HTTPException(status_code=400, detail="Invalid role")

        return profile

    finally:
        db.close()

def build_token_payload(user: User, profile: dict) -> dict:
    return {
        "id": user.id,           
        "role": user.role,
    }
    
