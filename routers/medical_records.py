from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from models.user import UserSchema
from models.medical_record import (
    MedicalRecordFullRequest, MedicalRecordFullResponse,
    MedicalRecordBucodentalExam, MedicalRecordCardiovascularExam, MedicalRecordClinicalExam,
    MedicalRecordData, MedicalRecordDataImg, MedicalRecordDerivations, MedicalRecordDigestiveExam,
    MedicalRecordEvaluationType, MedicalRecordFamilyHistory, MedicalRecordGenitourinarioExam,
    MedicalRecordHabits, MedicalRecordHeadExam, MedicalRecordImmunizations, MedicalRecordLaboralContacts,
    MedicalRecordLaboralExam, MedicalRecordLaboralHistory, MedicalRecordNeuroClinicalExam,
    MedicalRecordOftalmologicoExam, MedicalRecordOrlExam, MedicalRecordOsteoarticularExam,
    MedicalRecordPersonalHistory, MedicalRecordPreviousProblems, MedicalRecordPsychiatricClinicalExam,
    MedicalRecordRecomendations, MedicalRecordRespiratorioExam, MedicalRecordSignatures,
    MedicalRecordSkinExam, MedicalRecordStudies, MedicalRecordSurgerys, MedicalRecordLaboralSignatures
)
from auth.authentication import require_active_user, require_roles
from Database.getConnection import getConnectionForLogin
from sqlalchemy import text
from datetime import datetime
from typing import List, Optional, Annotated, Any, Dict
from pydantic import Json, ValidationError, BeforeValidator
import json
import uuid
import os
import shutil
from pathlib import Path
import json
from datetime import date

router = APIRouter(prefix="/medical-records", tags=["Medical Records"])

# Configuration for Signatures
SIGNATURES_DIR_ENV = os.getenv("SIGNATURES_DIR")
if SIGNATURES_DIR_ENV:
    SIGNATURES_DIR = Path(SIGNATURES_DIR_ENV)
elif os.name == 'posix':
    SIGNATURES_DIR = Path("/home/iweb/vitalis/data/signatures/")
else:
    # Default relative to this file: ./../../signatures
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    SIGNATURES_DIR = Path(os.path.join(BASE_DIR, "signatures"))

DOMAIN_URL = "https://saludvitalis.org/MdpuF8KsXiRArNlHtl6pXO2XyLSJMTQ8_Vitalis/api/signatures"

# Ensure signatures directory exists
try:
    os.makedirs(SIGNATURES_DIR, exist_ok=True)
except Exception as e:
    print(f"Warning: Could not create signatures directory: {e}")

# Configuration for Data Images
DATA_IMAGES_DIR_ENV = os.getenv("DATA_IMAGES_DIR")
if DATA_IMAGES_DIR_ENV:
    DATA_IMAGES_DIR = Path(DATA_IMAGES_DIR_ENV)
else:
    # Default relative to this file: ./../../data_images
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DATA_IMAGES_DIR = Path(os.path.join(BASE_DIR, "data_images"))

# Ensure data images directory exists
try:
    os.makedirs(DATA_IMAGES_DIR, exist_ok=True)
except Exception as e:
    print(f"Warning: Could not create data images directory: {e}")

DATA_IMAGES_DOMAIN_URL = "https://saludvitalis.org/MdpuF8KsXiRArNlHtl6pXO2XyLSJMTQ8_Vitalis/api/data_images"


def _get_professional_id(db, user_id: str) -> Optional[str]:
    row = db.execute(
        text("SELECT id FROM professionals WHERE user_id = :uid LIMIT 1"),
        {"uid": user_id}
    ).mappings().first()
    if not row:
        # If user is admin (which is allowed in create), they might not have a professional ID.
        # But for signatures we typically need one. We'll handle this in the route.
        return None
    return row["id"]

def delete_physical_file(file_url: str, base_directory: Path):
    """
    Extrae el nombre del archivo de la URL y lo elimina del sistema de archivos.
    """
    if not file_url:
        return

    try:
        # Asumimos que la URL termina en /nombre_archivo.ext
        filename = file_url.split("/")[-1]
        file_path = base_directory / filename
        
        if file_path.exists():
            os.remove(file_path)
            print(f"File deleted: {file_path}")
        else:
            print(f"File not found on disk: {file_path}")
    except Exception as e:
        print(f"Error deleting file {file_url}: {e}")

@router.post("/", response_model=dict)
async def create_medical_record(
    patient_id: str = Form(...),
    data: Json[MedicalRecordFullRequest] = Form(...),
    data_img: UploadFile = File(None),
    firma_medico_evaluador: UploadFile = File(None),
    fecha_medico_evaluador: date = Form(...),
    firma_medico_laboral: UploadFile = File(None),
    fecha_medico_laboral: date = Form(...),
    current_user: UserSchema = Depends(require_roles("professional", "admin"))
):
    """
    Create a complete medical record.
    - **patient_id**: The ID of the patient.
    - **data**: A JSON string matching `MedicalRecordFullRequest`.
    - **data_img**: Optional image for medical record data.
    - **file**: Optional signature image file.
    """
    request_model = data

    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
        
    try:
        # 2. Check Patient
        patient = db.execute(
            text("SELECT id, company_id FROM patients WHERE id = :pid"),
            {"pid": patient_id}
        ).mappings().first()
        
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")

        # 3. Handle Signature File if present
        signature_url = None
        if firma_medico_evaluador:
            try:
                # Generate unique filename
                filename_str = firma_medico_evaluador.filename or "signature.png"
                file_ext = os.path.splitext(filename_str)[1]
                filename = f"sig_{uuid.uuid4()}{file_ext}"
                file_path = SIGNATURES_DIR / filename
                
                with open(file_path, "wb") as buffer:
                    shutil.copyfileobj(firma_medico_evaluador.file, buffer)
                
                # Construct URL
                # If DOMAIN_URL ends with /, don't add another.
                base_url = DOMAIN_URL.rstrip("/")
                signature_url = f"{base_url}/{filename}"
            except Exception as e:
                print(f"Error saving signature: {e}")
                # Continue without signature or fail? 
                # User requirement said "pide una imagen para luego guardarla". 
                # If it fails, maybe we should fail.
                raise HTTPException(status_code=500, detail=f"Error saving signature file: {str(e)}")

        # 3a. Handle Laboral Signature File if present
        laboral_signature_url = None
        if firma_medico_laboral:
            try:
                # Generate unique filename
                filename_str = firma_medico_laboral.filename or "signature_laboral.png"
                file_ext = os.path.splitext(filename_str)[1]
                filename = f"sig_lab_{uuid.uuid4()}{file_ext}"
                file_path = SIGNATURES_DIR / filename
                
                with open(file_path, "wb") as buffer:
                    shutil.copyfileobj(firma_medico_laboral.file, buffer)
                
                # Construct URL
                base_url = DOMAIN_URL.rstrip("/")
                laboral_signature_url = f"{base_url}/{filename}"
            except Exception as e:
                print(f"Error saving laboral signature: {e}")
                raise HTTPException(status_code=500, detail=f"Error saving laboral signature file: {str(e)}")

        # 3b. Handle Data Image File if present
        data_img_url = None
        if data_img:
            try:
                # Generate unique filename
                filename_str = data_img.filename or "data_img.png"
                file_ext = os.path.splitext(filename_str)[1]
                filename = f"data_{uuid.uuid4()}{file_ext}"
                file_path = DATA_IMAGES_DIR / filename 
                
                with open(file_path, "wb") as buffer:
                    shutil.copyfileobj(data_img.file, buffer)
                
                # Construct URL
                base_url = DATA_IMAGES_DOMAIN_URL.rstrip("/")
                data_img_url = f"{base_url}/{filename}"
            except Exception as e:
                print(f"Error saving data image: {e}")
                raise HTTPException(status_code=500, detail=f"Error saving data image file: {str(e)}")

        # 4. Insert Main Record
        record_id = str(uuid.uuid4())
        
        # 'medical_record' table only has id and patient_id in new schema
        db.execute(text("""
            INSERT INTO medical_record (id, patient_id)
            VALUES (:id, :patient_id)
        """), {
            "id": record_id,
            "patient_id": patient_id
        })

        # 5. Insert Sub-tables
        # We iterate over the fields of the request_model
        model_dump = request_model.model_dump(exclude_unset=True)
        
        # Helper to insert generic sub-table
        def insert_sub_table(table_name: str, data_dict: dict, inject_medical_record_id: bool = True):
            if not data_dict:
                return
            
            # Prepare data
            data_dict["id"] = str(uuid.uuid4())
            if inject_medical_record_id:
                data_dict["medical_record_id"] = record_id
            
            # Construct Query dynamically
            columns = list(data_dict.keys())
            values_placeholders = [f":{col}" for col in columns]
            
            query = f"""
                INSERT INTO {table_name} ({', '.join(columns)})
                VALUES ({', '.join(values_placeholders)})
            """
            
            db.execute(text(query), data_dict)

        # Iterate through all fields in the request model
        # The field names in Pydantic match the Table names exactly (e.g. medical_record_clinical_exam)
        mr_data_id = None
        
        # KEY: We must insert medical_record_data FIRST if it exists, to get its ID for medical_record_data_img
        if request_model.medical_record_data:
             data_dict = request_model.medical_record_data.model_dump(exclude_unset=True)
             if data_dict:
                 # Always generate a new ID for the new record data, ignoring client input to prevent collisions
                 mr_data_id = str(uuid.uuid4())
                 data_dict["id"] = mr_data_id
                 
                 data_dict["medical_record_id"] = record_id
                 
                 # Insert manual
                 cols = list(data_dict.keys())
                 vals = [f":{col}" for col in cols]
                 query = f"INSERT INTO medical_record_data ({', '.join(cols)}) VALUES ({', '.join(vals)})"
                 db.execute(text(query), data_dict)

                 # Insert Data Image if exists
                 if data_img_url:
                     img_data = {
                         "id": str(uuid.uuid4()),
                         "medical_record_data_id": mr_data_id,
                         "url": data_img_url
                     }
                     db.execute(
                         text("INSERT INTO medical_record_data_img (id, medical_record_data_id, url) VALUES (:id, :medical_record_data_id, :url)"),
                         img_data
                     )

        for field_name, field_value in model_dump.items():
            if field_name == "medical_record_signatures": 
                continue 
            
            if field_name == "medical_record_laboral_signatures":
                continue

            
            if field_name == "medical_record_data":
                continue # Already handled
                
            if field_name == "medical_record_data_img":
                # Handle dependency
                if field_value and mr_data_id:
                     field_value["medical_record_data_id"] = mr_data_id
                     # Remove medical_record_id if Pydantic added it (it shouldn't have it in model? check model)
                     # Model: MedicalRecordDataImg(id, medical_record_data_id, url)
                     # It does NOT have medical_record_id. Good.
                     
                     insert_sub_table(field_name, field_value, inject_medical_record_id=False)
                continue

            if field_value:
                 insert_sub_table(field_name, field_value)

        # 6. Insert Signature
        # Logic: 
        # - If file provided -> Create new signature entry with URL.
        # - If JSON `medical_record_signatures` provided -> Use it? 
        # - Merge them?
        # The user said "menos la que dice medical_records_signature que no solo aparece en el JSON si no que pide una imagen".
        # This implies we should merge.
        
        sig_data = model_dump.get("medical_record_signatures", {}) or {}
        if signature_url:
            sig_data["url"] = signature_url
        
        if sig_data or signature_url: # Only insert if we have something
            sig_data["id"] = str(uuid.uuid4())
            sig_data["medical_record_id"] = record_id
            sig_data["created_at"] = fecha_medico_evaluador
            
            # Get professional ID
            prof_id = None
            if current_user.role == "professional":
                prof_id = _get_professional_id(db, current_user.id)
            if prof_id:
                sig_data["professional_id"] = prof_id
            
            # If professional_id was in JSON, it takes precedence? Or ours? 
            # I'll let the JSON override if present, otherwise use Auth.
            
            columns = list(sig_data.keys())
            values_placeholders = [f":{col}" for col in columns]
            query = f"""
                INSERT INTO medical_record_signatures ({', '.join(columns)})
                VALUES ({', '.join(values_placeholders)})
            """
            db.execute(text(query), sig_data)

        # 7. Insert Laboral Signature
        lab_sig_data = model_dump.get("medical_record_laboral_signatures", {}) or {}
        if laboral_signature_url:
             lab_sig_data["url"] = laboral_signature_url
        
        if lab_sig_data or laboral_signature_url:
            lab_sig_data["id"] = str(uuid.uuid4())
            lab_sig_data["medical_record_id"] = record_id
            lab_sig_data["created_at"] = fecha_medico_laboral # Use the laboral date
            
            # Get professional ID
            prof_id = None
            if current_user.role == "professional":
                prof_id = _get_professional_id(db, current_user.id)
            if prof_id:
                 lab_sig_data["professional_id"] = prof_id
            
            columns = list(lab_sig_data.keys())
            values_placeholders = [f":{col}" for col in columns]
            query = f"""
                INSERT INTO medical_record_laboral_signatures ({', '.join(columns)})
                VALUES ({', '.join(values_placeholders)})
            """
            db.execute(text(query), lab_sig_data)

        db.commit()
        return {"id": record_id, "detail": "Medical record created successfully"}

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error creating medical record: {str(e)}")
    finally:
        db.close()


@router.get("/patient/{patient_id}", response_model=List[MedicalRecordFullResponse])
async def get_medical_records_by_patient(
    patient_id: str,
    current_user: UserSchema = Depends(require_active_user)
):
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
        
    try:
        # Get all parent records
        records = db.execute(
            text("SELECT id, patient_id FROM medical_record WHERE patient_id = :pid"),
            {"pid": patient_id}
        ).mappings().all()
        
        response_list = []
        
        table_names = [
            "medical_record_bucodental_exam", "medical_record_cardiovascular_exam", "medical_record_clinical_exam",
            "medical_record_data", "medical_record_data_img", "medical_record_derivations", "medical_record_digestive_exam",
            "medical_record_evaluation_type", "medical_record_family_history", "medical_record_genitourinario_exam",
            "medical_record_habits", "medical_record_head_exam", "medical_record_immunizations", "medical_record_laboral_contacts",
            "medical_record_laboral_exam", "medical_record_laboral_history", "medical_record_neuro_clinical_exam",
            "medical_record_oftalmologico_exam", "medical_record_orl_exam", "medical_record_osteoarticular_exam",
            "medical_record_personal_history", "medical_record_previous_problems", "medical_record_psychiatric_clinical_exam",
            "medical_record_recomendations", "medical_record_respiratorio_exam", "medical_record_signatures",
            "medical_record_skin_exam", "medical_record_studies", "medical_record_surgerys", "medical_record_laboral_signatures"
        ]
        
        for rec in records:
            full_rec = dict(rec) # Start with id, patient_id
            
            # For each sub-table, fetch the row
            for table in table_names:
                # Some tables might have multiple entries? 
                # Based on the singular naming in Pydantic models (Optional[Model]), we assume 1:1 for most.
                # But 'medical_record_signatures' could be many?
                # The prompt implies "Giant JSON" structure which usually matches the model hierarchy.
                # If the models have `Optional[Model]`, it implies 1:1.
                # If `List[Model]`, it implies 1:N.
                # My generated models use `Optional[MedicalRecord...]` for all tables.
                # So I will fetch .first()
                
                # Exception: `medical_record_data_img` links to `medical_record_data`.
                # If I fetch it here linking to `medical_record_id`, it will fail if the column doesn't exist.
                # `medical_record_data_img` has `medical_record_data_id` NOT `medical_record_id`.
                # So we can't fetch it directly with `medical_record_id`.
                # We need to fetch it via `medical_record_data`.
                
                if table == "medical_record_data_img":
                    continue # handled with data
                
                row = db.execute(
                    text(f"SELECT * FROM {table} WHERE medical_record_id = :rid LIMIT 1"),
                    {"rid": rec["id"]}
                ).mappings().first()
                
                if row:
                    full_rec[table] = dict(row)
            
            # Handle medical_record_data_img
            if "medical_record_data" in full_rec and full_rec["medical_record_data"]:
                data_id = full_rec["medical_record_data"]["id"]
                img_row = db.execute(
                    text("SELECT * FROM medical_record_data_img WHERE medical_record_data_id = :did LIMIT 1"),
                    {"did": data_id}
                ).mappings().first()
                if img_row:
                    full_rec["medical_record_data_img"] = dict(img_row)
                    
            response_list.append(full_rec)
            
        return response_list

    finally:
        db.close()

@router.delete("/{record_id}")
async def delete_medical_record(
    record_id: str,
    current_user: UserSchema = Depends(require_roles("admin", "professional"))
):
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
        
    try:
        # ---------------------------------------------------------
        # 1. Recuperar info de archivos ANTES de borrar la DB
        # ---------------------------------------------------------
        
        # A. Buscar firmas (Evaluador y Laboral)
        signatures = db.execute(
            text("SELECT url FROM medical_record_signatures WHERE medical_record_id = :rid"), 
            {"rid": record_id}
        ).mappings().all()
        
        laboral_signatures = db.execute(
            text("SELECT url FROM medical_record_laboral_signatures WHERE medical_record_id = :rid"), 
            {"rid": record_id}
        ).mappings().all()

        # B. Buscar Data Images (Es mas complejo porque requiere join o subquery)
        # Primero buscamos los IDs de medical_record_data asociados a este record
        data_rows = db.execute(
            text("SELECT id FROM medical_record_data WHERE medical_record_id = :rid"), 
            {"rid": record_id}
        ).mappings().all()
        
        data_images_urls = []
        for dr in data_rows:
            imgs = db.execute(
                text("SELECT url FROM medical_record_data_img WHERE medical_record_data_id = :did"),
                {"did": dr["id"]}
            ).mappings().all()
            for img in imgs:
                data_images_urls.append(img["url"])

        # ---------------------------------------------------------
        # 2. Eliminar archivos Físicos (Usando el helper)
        # ---------------------------------------------------------
        for sig in signatures:
            delete_physical_file(sig["url"], SIGNATURES_DIR)
            
        for l_sig in laboral_signatures:
            delete_physical_file(l_sig["url"], SIGNATURES_DIR)
            
        for img_url in data_images_urls:
            delete_physical_file(img_url, DATA_IMAGES_DIR)

        # ---------------------------------------------------------
        # 3. Borrado en Base de Datos (Cascada Manual)
        # ---------------------------------------------------------

        # A. Primero borrar medical_record_data_img (Nivel más profundo)
        # Usamos los data_rows que recuperamos arriba para ser eficientes
        for dr in data_rows: 
            db.execute(text("DELETE FROM medical_record_data_img WHERE medical_record_data_id = :did"), {"did": dr["id"]})
            
        # B. Borrar medical_record_data
        db.execute(text("DELETE FROM medical_record_data WHERE medical_record_id = :rid"), {"rid": record_id})
        
        # C. Borrar el resto de tablas hijas
        table_names = [
            "medical_record_bucodental_exam", "medical_record_cardiovascular_exam", "medical_record_clinical_exam",
            "medical_record_derivations", "medical_record_digestive_exam",
            "medical_record_evaluation_type", "medical_record_family_history", "medical_record_genitourinario_exam",
            "medical_record_habits", "medical_record_head_exam", "medical_record_immunizations", "medical_record_laboral_contacts",
            "medical_record_laboral_exam", "medical_record_laboral_history", "medical_record_neuro_clinical_exam",
            "medical_record_oftalmologico_exam", "medical_record_orl_exam", "medical_record_osteoarticular_exam",
            "medical_record_personal_history", "medical_record_previous_problems", "medical_record_psychiatric_clinical_exam",
            "medical_record_recomendations", "medical_record_respiratorio_exam", "medical_record_signatures",
            "medical_record_skin_exam", "medical_record_studies", "medical_record_surgerys", "medical_record_laboral_signatures"
        ]
        
        for table in table_names:
            db.execute(text(f"DELETE FROM {table} WHERE medical_record_id = :rid"), {"rid": record_id})
            
        # D. Finalmente, borrar el registro padre
        db.execute(text("DELETE FROM medical_record WHERE id = :rid"), {"rid": record_id})
        
        db.commit()
        return {"detail": "Record and associated files deleted successfully"}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@router.put("/{record_id}")
async def update_medical_record(
    record_id: str,
    patient_id: str = Form(...),
    data: Json[MedicalRecordFullRequest] = Form(...),
    data_img: UploadFile = File(None), 
    firma_medico_evaluador: UploadFile = File(None),
    fecha_medico_evaluador: Optional[date] = Form(None),
    firma_medico_laboral: UploadFile = File(None),
    fecha_medico_laboral: Optional[date] = Form(None),
    current_user: UserSchema = Depends(require_roles("professional", "admin"))
):
    request_model = data
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
        
    try:
        # Check record logic (igual que tenias)
        curr = db.execute(text("SELECT id FROM medical_record WHERE id = :id"), {"id": record_id}).fetchone()
        if not curr:
            raise HTTPException(status_code=404, detail="Medical record not found")

        # Update parent patient_id (igual que tenias)
        db.execute(text("UPDATE medical_record SET patient_id = :pid WHERE id = :rid"), {"pid": patient_id, "rid": record_id})
        
        # -------------------------------------------------
        # Lógica de Sub-tablas (Tu loop original)
        # -------------------------------------------------
        model_dump = request_model.model_dump(exclude_unset=True)
        
        # Necesitamos capturar el ID de medical_record_data si existe o se crea
        # para poder asociar la imagen data_img
        mr_data_id = None 

        for field_name, field_value in model_dump.items():
            if field_name in ["medical_record_signatures", "medical_record_laboral_signatures", "medical_record_data_img"]:
                continue 

            # Lógica especial para capturar el ID de medical_record_data
            if field_name == "medical_record_data":
                # Verificamos si existe
                existing_data = db.execute(text("SELECT id FROM medical_record_data WHERE medical_record_id = :rid"), {"rid": record_id}).mappings().first()
                
                if existing_data:
                    mr_data_id = existing_data["id"] # Guardamos ID existente
                    # ... lógica de update estándar ...
                else:
                    # ... lógica de insert estándar ...
                    # Si insertas uno nuevo, asegúrate de guardar el nuevo ID en mr_data_id
                    pass
            
            # ... (Aquí va tu lógica original del loop update/insert de tablas genéricas) ...
            # NOTA: Asegúrate de que si field_name == "medical_record_data", asignes mr_data_id = field_value["id"] o el ID que recuperes.

            # PEGAR AQUÍ TU LÓGICA DE UPDATE/INSERT DE SUBTABLAS EXISTENTE
            # (Resumida para brevedad, pero usa tu código original del bloque `for field_name...`)
            if field_value:
                 # ... tu logica existente ...
                 pass

        # Si no encontramos mr_data_id en el loop (porque no venía en el JSON), lo buscamos ahora
        if not mr_data_id:
            existing_data_row = db.execute(text("SELECT id FROM medical_record_data WHERE medical_record_id = :rid"), {"rid": record_id}).mappings().first()
            if existing_data_row:
                mr_data_id = existing_data_row["id"]

        # -------------------------------------------------
        # 1. Update DATA IMAGE (Lo que faltaba)
        # -------------------------------------------------
        if data_img and mr_data_id:
            try:
                # A. Buscar imagen vieja
                existing_img = db.execute(
                    text("SELECT id, url FROM medical_record_data_img WHERE medical_record_data_id = :did"),
                    {"did": mr_data_id}
                ).mappings().first()

                # B. Borrar imagen vieja fisica y registro
                if existing_img:
                    delete_physical_file(existing_img["url"], DATA_IMAGES_DIR)
                    db.execute(text("DELETE FROM medical_record_data_img WHERE id = :id"), {"id": existing_img["id"]})

                # C. Guardar imagen nueva
                filename_str = data_img.filename or "data_updated.png"
                file_ext = os.path.splitext(filename_str)[1]
                filename = f"data_{uuid.uuid4()}{file_ext}"
                file_path = DATA_IMAGES_DIR / filename
                
                with open(file_path, "wb") as buffer:
                    shutil.copyfileobj(data_img.file, buffer)
                
                new_url = f"{DATA_IMAGES_DOMAIN_URL.rstrip('/')}/{filename}"

                # D. Insertar nuevo registro
                db.execute(
                    text("INSERT INTO medical_record_data_img (id, medical_record_data_id, url) VALUES (:id, :did, :url)"),
                    {"id": str(uuid.uuid4()), "did": mr_data_id, "url": new_url}
                )

            except Exception as e:
                print(f"Error updating data image: {e}")
                # No lanzamos error 500 para no romper todo el update, pero logueamos.

        # -------------------------------------------------
        # 2. Update FIRMA EVALUADOR (Refactorizado)
        # -------------------------------------------------
        if firma_medico_evaluador:
            try:
                # A. Buscar vieja
                existing_sig = db.execute(text("SELECT id, url FROM medical_record_signatures WHERE medical_record_id = :rid"), {"rid": record_id}).mappings().first()
                
                # B. Borrar vieja
                if existing_sig:
                    delete_physical_file(existing_sig["url"], SIGNATURES_DIR) # Usando Helper
                    db.execute(text("DELETE FROM medical_record_signatures WHERE id = :id"), {"id": existing_sig["id"]})

                # C. Guardar nueva
                filename = f"sig_{uuid.uuid4()}{os.path.splitext(firma_medico_evaluador.filename or '')[1]}"
                file_path = SIGNATURES_DIR / filename
                with open(file_path, "wb") as buffer:
                    shutil.copyfileobj(firma_medico_evaluador.file, buffer)
                
                new_url = f"{DOMAIN_URL.rstrip('/')}/{filename}"
                prof_id = _get_professional_id(db, current_user.id)

                # D. Insertar
                sig_data = {
                    "id": str(uuid.uuid4()), "medical_record_id": record_id, "url": new_url,
                    "professional_id": prof_id,
                    "created_at": fecha_medico_evaluador if fecha_medico_evaluador else datetime.utcnow()
                }
                # ... Query de insert (igual que tenías) ...
                keys = list(sig_data.keys())
                vals = [f":{k}" for k in keys]
                db.execute(text(f"INSERT INTO medical_record_signatures ({', '.join(keys)}) VALUES ({', '.join(vals)})"), sig_data)

            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Error signature update: {e}")

        # -------------------------------------------------
        # 3. Update FIRMA LABORAL (Refactorizado)
        # -------------------------------------------------
        if firma_medico_laboral:
            try:
                # A. Buscar vieja
                existing_lab = db.execute(text("SELECT id, url FROM medical_record_laboral_signatures WHERE medical_record_id = :rid"), {"rid": record_id}).mappings().first()
                
                # B. Borrar vieja
                if existing_lab:
                    delete_physical_file(existing_lab["url"], SIGNATURES_DIR) # Usando Helper
                    db.execute(text("DELETE FROM medical_record_laboral_signatures WHERE id = :id"), {"id": existing_lab["id"]})

                # C. Guardar nueva
                filename = f"sig_lab_{uuid.uuid4()}{os.path.splitext(firma_medico_laboral.filename or '')[1]}"
                file_path = SIGNATURES_DIR / filename
                with open(file_path, "wb") as buffer:
                    shutil.copyfileobj(firma_medico_laboral.file, buffer)

                new_url = f"{DOMAIN_URL.rstrip('/')}/{filename}"
                prof_id = _get_professional_id(db, current_user.id)

                # D. Insertar
                lab_data = {
                    "id": str(uuid.uuid4()), "medical_record_id": record_id, "url": new_url,
                    "professional_id": prof_id,
                    "created_at": fecha_medico_laboral if fecha_medico_laboral else datetime.utcnow()
                }
                # ... Query de insert ...
                keys = list(lab_data.keys())
                vals = [f":{k}" for k in keys]
                db.execute(text(f"INSERT INTO medical_record_laboral_signatures ({', '.join(keys)}) VALUES ({', '.join(vals)})"), lab_data)

            except Exception as e:
                 raise HTTPException(status_code=500, detail=f"Error laboral signature update: {e}")

        db.commit()
        return {"detail": "Updated successfully with file management"}

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()