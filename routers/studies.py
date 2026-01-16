from fastapi import APIRouter, Depends, HTTPException, status, Form, UploadFile, File, Query
from fastapi.responses import FileResponse
from models.user import User
from auth.authentication import require_active_user, require_roles
from Database.getConnection import getConnectionForLogin
from sqlalchemy import text
from datetime import datetime
import uuid
import os
from typing import Optional
import shutil

router = APIRouter(prefix="/studies", tags=["Studies"])

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if os.name == 'posix':
    STUDIES_DIR = "/home/iweb/vitalis/data/studies/"
else:
    STUDIES_DIR = os.path.join(PROJECT_ROOT, "studies")
os.makedirs(STUDIES_DIR, exist_ok=True)

def _format_study(row) -> dict:
    return {
        "id": row["id"],
        "patient_id": row["patient_id"],
        "professional_id": row["professional_id"],
        "created_by_user_id": row["created_by_user_id"],
        "study_type": row["study_type"],
        "title": row["title"],
        "description": row["description"],
        "description": row["description"],
        # "status": row["status"], # Removed as column doesn't exist
        "created_at": row.get("created_at"),
    }

def _check_access_to_patient(current_user: User, patient_id: str, db):
    patient = db.execute(
        text("SELECT id, company_id, user_id FROM patients WHERE id = :pid"),
        {"pid": patient_id}
    ).mappings().first()
    
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    if current_user.role == "patient":
        if patient["user_id"] != current_user.id:
            raise HTTPException(status_code=403, detail="You can only view your own studies")
    elif current_user.role == "professional":
        pass
    elif current_user.role == "company":
        company = db.execute(
            text("SELECT id FROM companies WHERE owner_user_id = :uid"),
            {"uid": current_user.id}
        ).mappings().first()
        if not company or patient["company_id"] != company["id"]:
            raise HTTPException(status_code=403, detail="You can only view your employees' studies")
    elif current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    return patient

@router.post("/patient/{patient_id}", tags=["Studies"])
async def create_study(
    patient_id: str,
    study_type: str = Form(default=""),
    title: str = Form(default=""),
    description: str = Form(default=""),
    # status: str = Form(default="pending"), # Removed
    current_user: User = Depends(require_roles("professional", "admin"))
):
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        patient = db.execute(
            text("SELECT id FROM patients WHERE id = :pid"),
            {"pid": patient_id}
        ).mappings().first()
        
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")
        
        study_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        
        professional_id = None
        if current_user.role == "professional":
            prof = db.execute(
                text("SELECT id FROM professionals WHERE user_id = :uid LIMIT 1"),
                {"uid": current_user.id}
            ).mappings().first()
            if prof:
                professional_id = prof["id"]
        
        db.execute(text("""
            INSERT INTO studies
            (id, patient_id, professional_id, created_by_user_id, study_type, title, description, created_at)
            VALUES (:id, :patient_id, :professional_id, :created_by_user_id, :study_type, :title, :description, :created_at)
        """), {
            "id": study_id,
            "patient_id": patient_id,
            "professional_id": professional_id,
            "created_by_user_id": current_user.id,
            "study_type": study_type,
            "title": title,
            "description": description,
            # "status": status,
            "created_at": now,
        })
        
        db.commit()
        
        return {
            "detail": "Study created successfully",
            "study_id": study_id,
            "patient_id": patient_id,
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Error creating study" + str(e))
    finally:
        db.close()

@router.get("/", tags=["Studies"])
async def get_studies(
    patient_id: str = Query(None),
    current_user: User = Depends(require_active_user)
):
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        if not patient_id:
            raise HTTPException(status_code=400, detail="patient_id is required")
        
        _check_access_to_patient(current_user, patient_id, db)
        
        rows = db.execute(
            text("""
                SELECT id, patient_id, professional_id, created_by_user_id, study_type, 
                       title, description, created_at
                FROM studies
                WHERE patient_id = :pid
                ORDER BY created_at DESC
            """),
            {"pid": patient_id}
        ).mappings().all()
        
        studies = [_format_study(row) for row in rows]
        return {"patient_id": patient_id, "studies": studies, "total": len(studies)}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error fetching studies")
    finally:
        db.close()

@router.get("/{study_id}", tags=["Studies"])
async def get_study(study_id: str, current_user: User = Depends(require_active_user)):
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        row = db.execute(
            text("""
                SELECT id, patient_id, professional_id, created_by_user_id, study_type, 
                       title, description, created_at
                FROM studies
                WHERE id = :sid
            """),
            {"sid": study_id}
        ).mappings().first()
        
        if not row:
            raise HTTPException(status_code=404, detail="Study not found")
        
        _check_access_to_patient(current_user, row["patient_id"], db)
        
        study = _format_study(row)
        
        files = db.execute(
            text("""
                SELECT id, study_id, file_path, original_filename, mime_type, size_bytes, uploaded_at
                FROM study_files
                WHERE study_id = :sid
            """),
            {"sid": study_id}
        ).mappings().all()
        
        study["files"] = [
            {
                "id": f["id"],
                "filename": f["original_filename"],
                "mime_type": f["mime_type"],
                "size_bytes": f["size_bytes"],
                "uploaded_at": f["uploaded_at"],
            } for f in files
        ]
        
        return study
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error fetching study")
    finally:
        db.close()

@router.patch("/{study_id}", tags=["Studies"])
async def update_study(
    study_id: str,
    study_type: str = Form(default=None),
    title: str = Form(default=None),
    description: str = Form(default=None),
    # status: str = Form(default=None),
    current_user: User = Depends(require_roles("professional", "admin"))
):
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        row = db.execute(
            text("SELECT created_by_user_id FROM studies WHERE id = :sid"),
            {"sid": study_id}
        ).mappings().first()
        
        if not row:
            raise HTTPException(status_code=404, detail="Study not found")
        
        if current_user.role != "admin" and row["created_by_user_id"] != current_user.id:
            raise HTTPException(status_code=403, detail="You can only modify your own studies")
        
        updates = []
        params = {"sid": study_id}
        
        if study_type is not None:
            updates.append("study_type = :study_type")
            params["study_type"] = study_type
        if title is not None:
            updates.append("title = :title")
            params["title"] = title
        if description is not None:
            updates.append("description = :description")
            params["description"] = description
        # if status is not None:
        #     updates.append("status = :status")
        #     params["status"] = status
        
        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")
        
        db.execute(
            text(f"UPDATE studies SET {', '.join(updates)} WHERE id = :sid"),
            params
        )
        db.commit()
        
        return {"detail": "Study updated successfully", "study_id": study_id}
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Error updating study")
    finally:
        db.close()

@router.delete("/{study_id}", tags=["Studies"])
async def delete_study(
    study_id: str,
    current_user: User = Depends(require_roles("admin"))
):
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        study = db.execute(
            text("SELECT id FROM studies WHERE id = :sid"),
            {"sid": study_id}
        ).mappings().first()
        
        if not study:
            raise HTTPException(status_code=404, detail="Study not found")
        
        files = db.execute(
            text("SELECT file_path FROM study_files WHERE study_id = :sid"),
            {"sid": study_id}
        ).mappings().all()
        
        for f in files:
            try:
                if os.path.exists(f["file_path"]):
                    os.remove(f["file_path"])
            except Exception:
                pass
        
        db.execute(text("DELETE FROM study_files WHERE study_id = :sid"), {"sid": study_id})
        db.execute(text("DELETE FROM studies WHERE id = :sid"), {"sid": study_id})
        db.commit()
        
        return {"detail": "Study deleted successfully", "study_id": study_id}
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Error deleting study")
    finally:
        db.close()

@router.post("/{study_id}/files", tags=["Studies"])
async def upload_study_file(
    study_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(require_active_user)
):
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        study = db.execute(
            text("SELECT id, patient_id, created_by_user_id FROM studies WHERE id = :sid"),
            {"sid": study_id}
        ).mappings().first()
        
        if not study:
            raise HTTPException(status_code=404, detail="Study not found")
        
        if current_user.role not in ("admin", "professional"):
            raise HTTPException(status_code=403, detail="Only admin or professionals can upload files")
        
        os.makedirs(STUDIES_DIR, exist_ok=True)
        
        file_id = str(uuid.uuid4())
        file_extension = os.path.splitext(file.filename)[1]
        stored_filename = f"{file_id}{file_extension}"
        file_path = os.path.join(STUDIES_DIR, stored_filename)
        
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        size_bytes = len(content)
        now = datetime.utcnow().isoformat()
        
        db.execute(text("""
            INSERT INTO study_files
            (id, study_id, file_path, original_filename, mime_type, size_bytes, uploaded_at)
            VALUES (:id, :study_id, :file_path, :original_filename, :mime_type, :size_bytes, :uploaded_at)
        """), {
            "id": file_id,
            "study_id": study_id,
            "file_path": file_path,
            "original_filename": file.filename,
            "mime_type": file.content_type,
            "size_bytes": size_bytes,
            "uploaded_at": now,
        })
        
        db.commit()
        
        return {
            "detail": "File uploaded successfully",
            "file_id": file_id,
            "filename": file.filename,
            "size_bytes": size_bytes,
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except:
            pass
        raise HTTPException(status_code=500, detail="Error uploading file")
    finally:
        db.close()
        
@router.get("/{study_id}/files")
async def download_study_file(
    study_id: str,
    current_user: User = Depends(require_active_user)
):
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        # JOIN con la tabla correcta: study_files (sin 's' al final)
        result = db.execute(
            text("""
                SELECT 
                    s.id,
                    s.patient_id,
                    sf.file_path,
                    sf.original_filename,
                    sf.mime_type
                FROM studies s
                INNER JOIN study_files sf ON s.id = sf.study_id
                WHERE s.id = :study_id
            """),
            {"study_id": study_id}
        ).mappings().first()
        
        if not result:
            raise HTTPException(status_code=404, detail="Study not found")
        
        # Verificar permisos
        if current_user.role == "patient":
            if result["patient_id"] != current_user.patient_id:
                raise HTTPException(status_code=403, detail="Access denied")
        
        # Verificar que el archivo existe
        file_path = result["file_path"]
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="File not found")
        
        # Devolver el archivo
        return FileResponse(
            path=file_path,
            filename=result["original_filename"],
            media_type=result["mime_type"]
        )
        
    finally:
        db.close()

@router.delete("/{study_id}/files/{file_id}", tags=["Studies"])
async def delete_study_file(
    study_id: str,
    file_id: str,
    current_user: User = Depends(require_roles("admin"))
):
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        file_row = db.execute(
            text("SELECT file_path FROM study_files WHERE id = :fid AND study_id = :sid"),
            {"fid": file_id, "sid": study_id}
        ).mappings().first()
        
        if not file_row:
            raise HTTPException(status_code=404, detail="File not found")
        
        try:
            if os.path.exists(file_row["file_path"]):
                os.remove(file_row["file_path"])
        except Exception:
            pass
        
        db.execute(
            text("DELETE FROM study_files WHERE id = :fid"),
            {"fid": file_id}
        )
        db.commit()
        
        return {"detail": "File deleted successfully", "file_id": file_id}
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Error deleting file")
    finally:
        db.close()
