from os import name
from Database.getConnection import engine
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status, Form, UploadFile, File, Query
from models.user import User
from auth.authentication import require_active_user, require_roles
from Database.getConnection import getConnectionForLogin
from sqlalchemy import text
from datetime import datetime
import uuid
import os
from typing import Optional
import shutil
from typing import List

router = APIRouter(prefix="/studies")

STUDIES_DIR = os.getenv("STUDIES_DIR", "/home/iweb/vitalis/data/studies/")
if os.name != 'posix' and not os.getenv("STUDIES_DIR"):
     # Fallback for windows dev
     PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
     STUDIES_DIR = os.path.join(PROJECT_ROOT, "studies")
     
DOMAIN_URL = "https://saludvitalis.org/MdpuF8KsXiRArNlHtl6pXO2XyLSJMTQ8_Vitalis/api/studies/files"

STUDIES_ADMIN_DIR = os.getenv("STUDIES_ADMIN_DIR", "/home/iweb/vitalis/data/studies_admin/")
if os.name != 'posix' and not os.getenv("STUDIES_ADMIN_DIR"):
     # Fallback for windows dev
     PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
     STUDIES_ADMIN_DIR = os.path.join(PROJECT_ROOT, "studies_admin")
     
# Ensure studies admin directory exists
try:
    os.makedirs(STUDIES_ADMIN_DIR, exist_ok=True)
except Exception as e:
    print(f"Warning: Could not create studies admin directory: {e}")

DOMAIN_URL_ADMIN = "https://saludvitalis.org/MdpuF8KsXiRArNlHtl6pXO2XyLSJMTQ8_Vitalis/api/studies_admin/files"

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
    
    return patient

@router.post("/patient/{patient_id}", tags=["Studies"])
async def create_study(
    patient_id: str,
    study_type: str = Form(...),
    status: str = Form(...),
    study_files: List[UploadFile] = File(...),
    current_user: User = Depends(require_roles("admin", "professional"))
):
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")

    try:
        study_id = str(uuid.uuid4())
        created_at = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')

        # Insert Study
        db.execute(
            text("""
                INSERT INTO studies (id, patient_id, created_by_user_id, study_type, status, created_at)
                VALUES (:id, :patient_id, :created_by_user_id, :study_type, :status, :created_at)
            """),
            {
                "id": study_id,
                "patient_id": patient_id,
                "created_by_user_id": current_user.id,
                "study_type": study_type,
                "status": status,
                "created_at": created_at
            }
        )

        uploaded_files_data = []

        # Process Files
        for file in study_files:
            if not os.path.exists(STUDIES_DIR):
                os.makedirs(STUDIES_DIR, exist_ok=True)
            
            # Normalize filename and ensure uniqueness
            ext = os.path.splitext(file.filename or "file.pdf")[1].lower()
            fname = f"{uuid.uuid4()}{ext}"
            path = os.path.join(STUDIES_DIR, fname)
            
            # Save file
            content = await file.read()
            with open(path, "wb") as f:
                f.write(content)
                
            size_bytes = len(content)
            url_main = f"{DOMAIN_URL}/{fname}"
            file_id = str(uuid.uuid4())
            now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
            
            # Insert File Record
            db.execute(
                text("""
                    INSERT INTO study_files (id, study_id, file_path, original_filename, mime_type, size_bytes, uploaded_at)
                    VALUES (:id, :study_id, :file_path, :original_filename, :mime_type, :size_bytes, :uploaded_at)
                """),
                {
                    "id": file_id,
                    "study_id": study_id,
                    "file_path": path,
                    "original_filename": file.filename,
                    "mime_type": file.content_type,
                    "size_bytes": size_bytes,
                    "uploaded_at": now
                }
            )
            
            uploaded_files_data.append({
                "id": file_id,
                "url": url_main,
                "filename": file.filename
            })

        db.commit()
        return {
            "message": "Study created successfully",
            "id": study_id,
            "files": uploaded_files_data
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error creating study: {str(e)}")
    finally:
        db.close()

@router.get("/{patient_id}", tags=["Studies"])
async def get_studies(patient_id: str):
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        rows = db.execute(
            text("""
                SELECT id, patient_id, created_by_user_id, study_type, status, created_at
                FROM studies
                WHERE patient_id = :patient_id
                ORDER BY created_at DESC
            """),
            {"patient_id": patient_id}
        ).mappings().all()
        
        if not rows:
            return {"studies": [], "total": 0}

        # Studies files
        # Fetch files for all studies matching the patient_id (which is safer and cleaner than passing a list of IDs)
        files_rows = db.execute(
            text("""
                SELECT id, study_id, file_path, original_filename, mime_type, size_bytes, uploaded_at
                FROM study_files
                WHERE study_id IN (
                    SELECT id FROM studies WHERE patient_id = :patient_id
                )
            """),
            {"patient_id": patient_id}
        ).mappings().all() 
        
        # Group files by study_id
        files_by_study = {}
        for f in files_rows:
            sid = f["study_id"]
            if sid not in files_by_study:
                files_by_study[sid] = []
            files_by_study[sid].append(f)
        
        studies = []
        for row in rows:
            sid = row["id"]
            studies.append({
                "id": sid,
                "patient_id": row["patient_id"],
                "created_by_user_id": row["created_by_user_id"],
                "study_type": row["study_type"],
                "status": row["status"],
                "created_at": row["created_at"],
                "files": files_by_study.get(sid, [])
            })
        
        return {"studies": studies, "total": len(studies)}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error fetching studies" + str(e))
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
                SELECT id, patient_id, professional_id, created_by_user_id, study_type, status, created_at
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
    status: str = Form(default=None),
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
        
        updates = []
        params = {"sid": study_id}
        
        if study_type is not None:
            updates.append("study_type = :study_type")
            params["study_type"] = study_type
        if status is not None:
            updates.append("status = :status")
            params["status"] = status
        
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
    
    file_path = None
    
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
        file_extension = os.path.splitext(file.filename or "")[1]
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
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
        except:
            pass
        raise HTTPException(status_code=500, detail="Error uploading file")
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

# Studies admin

@router.post("/admin/create_study_category", tags=["Studies Admin"])
async def create_study_category(
    name: str = Form(...),
    image: UploadFile = File(None),
):
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        id = str(uuid.uuid4())
        
        if image:
            file_id = str(uuid.uuid4())
            file_extension = os.path.splitext(image.filename or "")[1]
            stored_filename = f"{file_id}{file_extension}"
            file_path = os.path.join(STUDIES_ADMIN_DIR, stored_filename)
            
            with open(file_path, "wb") as f:
                content = await image.read()
                f.write(content)
            
            # Construct URL
            base_url = DOMAIN_URL_ADMIN.rstrip("/")
            url_image = f"{base_url}/{stored_filename}"
            
            db.execute(
                text("INSERT INTO studies_admin (id, name, url_image) VALUES (:id, :name, :url_image)"),
                {"id": id, "name": name, "url_image": url_image}
            )
        
        db.commit()
        
        return {"detail": "Study created successfully", "study_id": id}
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error creating study: {str(e)}")
    finally:
        db.close()
        
@router.get("/admin/get_study_categories", tags=["Studies Admin"])
async def get_study_categories():
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        result = db.execute(
            text("SELECT id, name, url_image FROM studies_admin")
        ).mappings().all()
        
        return {"studies_categories": [dict(row) for row in result]}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting study categories: {str(e)}")
    finally:
        db.close()

@router.put("/admin/update_study_category/{study_id}", tags=["Studies Admin"])
async def update_study_category(
    study_id: str,
    name: str = Form(...),
    image: UploadFile = File(None),
):
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        if image:
            # 1. Get current image URL
            current_study = db.execute(
                text("SELECT url_image FROM studies_admin WHERE id = :id"),
                {"id": study_id}
            ).mappings().first()
            
            if current_study and current_study["url_image"]:
                try:
                    # Parse filename from URL
                    old_filename = current_study["url_image"].split("/")[-1]
                    old_file_path = os.path.join(STUDIES_ADMIN_DIR, old_filename)
                    if os.path.exists(old_file_path):
                        os.remove(old_file_path)
                except Exception as e:
                    print(f"Error removing old study image: {e}")

            # 2. Save new image
            file_id = str(uuid.uuid4())
            file_extension = os.path.splitext(image.filename or "")[1]
            stored_filename = f"{file_id}{file_extension}"
            file_path = os.path.join(STUDIES_ADMIN_DIR, stored_filename)
            
            with open(file_path, "wb") as f:
                content = await image.read()
                f.write(content)
            
            # Construct URL
            base_url = DOMAIN_URL_ADMIN.rstrip("/")
            url_image = f"{base_url}/{stored_filename}"
            
            db.execute(
                text("UPDATE studies_admin SET name = :name, url_image = :url_image WHERE id = :id"),
                {"id": study_id, "name": name, "url_image": url_image}
            )
        else:
            # Only update name if no image provided
            db.execute(
                text("UPDATE studies_admin SET name = :name WHERE id = :id"),
                {"id": study_id, "name": name}
            )
        
        db.commit()
        
        return {"detail": "Study updated successfully", "study_id": study_id}
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error updating study: {str(e)}")
    finally:
        db.close()

@router.delete("/admin/delete_study_category/{study_id}", tags=["Studies Admin"])
async def delete_study_category(
    study_id: str,
    current_user: User = Depends(require_roles("admin"))
):
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        # 1. Get study info to delete image
        current_study = db.execute(
            text("SELECT url_image FROM studies_admin WHERE id = :id"),
            {"id": study_id}
        ).mappings().first()
        
        if current_study and current_study["url_image"]:
            try:
                # Parse filename from URL
                old_filename = current_study["url_image"].split("/")[-1]
                old_file_path = os.path.join(STUDIES_ADMIN_DIR, old_filename)
                if os.path.exists(old_file_path):
                    os.remove(old_file_path)
            except Exception as e:
                print(f"Error removing study image: {e}")
        
        # 2. Delete study from database
        db.execute(
            text("DELETE FROM studies_admin WHERE id = :id"),
            {"id": study_id}
        )
        db.commit()
        
        return {"detail": "Study deleted successfully", "study_id": study_id}
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error deleting study: {str(e)}")
    finally:
        db.close()