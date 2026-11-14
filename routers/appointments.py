from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from auth.authentication import require_active_user
from Database.getConnection import getConnectionForLogin
from models.user import UserSchema

router = APIRouter(prefix="/appointments", tags=["Appointments"])
SLOT_MINUTES = 30
OPENING = time(6, 0)
LAST_START = time(12, 0)


class AppointmentCreate(BaseModel):
    patient_id: str
    date: date
    time: str


def _db():
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="No se pudo conectar con la base de datos")
    return db


def _company_id(db, user_id):
    row = db.execute(text("SELECT id FROM companies WHERE owner_user_id = :uid"), {"uid": user_id}).mappings().first()
    return str(row["id"]) if row else None


def _slot_start(slot_date: date, slot_time: str) -> datetime:
    try:
        parsed = time.fromisoformat(slot_time)
    except ValueError:
        raise HTTPException(status_code=422, detail="El horario seleccionado no es válido")
    if slot_date.weekday() not in (2, 4):
        raise HTTPException(status_code=422, detail="Los turnos se realizan los miércoles y viernes")
    if parsed < OPENING or parsed > LAST_START or (parsed.minute not in (0, 30)) or parsed.second or parsed.microsecond:
        raise HTTPException(status_code=422, detail="Elegí un turno entre las 6:00 y las 12:00, cada 30 minutos")
    start_at = datetime.combine(slot_date, parsed)
    now_ar = datetime.now(ZoneInfo("America/Argentina/Buenos_Aires")).replace(tzinfo=None)
    if start_at <= now_ar:
        raise HTTPException(status_code=422, detail="No se pueden reservar turnos en el pasado")
    return start_at


def _format(row):
    return {
        "id": str(row["id"]),
        "patient_id": str(row["patient_id"]),
        "patient_name": f"{row['first_name']} {row['last_name']}".strip(),
        "dni": row["dni"],
        "phone": row["phone"],
        "email": row["email"],
        "company_id": str(row["company_id"]) if row["company_id"] else None,
        "company_name": row["company_name"],
        "start_at": row["start_at"].strftime("%Y-%m-%dT%H:%M:%S"),
        "end_at": row["end_at"].strftime("%Y-%m-%dT%H:%M:%S"),
        "status": row["status"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
    }


@router.get("/patients")
async def appointment_patients(current_user: UserSchema = Depends(require_active_user)):
    """Patients eligible for booking, scoped to the caller's role and company."""
    db = _db()
    try:
        if current_user.role == "patient":
            rows = db.execute(text("""
                SELECT p.id, p.first_name, p.last_name, p.dni, p.phone, p.user_id,
                       p.company_id, c.name AS company_name
                FROM patients p LEFT JOIN companies c ON c.id = p.company_id
                WHERE p.user_id = :uid
            """), {"uid": current_user.id}).mappings().all()
        elif current_user.role == "company":
            company_id = _company_id(db, current_user.id)
            if not company_id:
                return []
            rows = db.execute(text("""
                SELECT p.id, p.first_name, p.last_name, p.dni, p.phone, p.user_id,
                       p.company_id, c.name AS company_name
                FROM patients p LEFT JOIN companies c ON c.id = p.company_id
                WHERE p.company_id = :cid ORDER BY p.last_name, p.first_name
            """), {"cid": company_id}).mappings().all()
        elif current_user.role in ("admin", "secretary"):
            rows = db.execute(text("""
                SELECT p.id, p.first_name, p.last_name, p.dni, p.phone, p.user_id,
                       p.company_id, c.name AS company_name
                FROM patients p LEFT JOIN companies c ON c.id = p.company_id
                ORDER BY p.last_name, p.first_name
            """)).mappings().all()
        else:
            raise HTTPException(status_code=403, detail="No tenés permiso para gestionar turnos")
        return [{"id": str(r["id"]), "first_name": r["first_name"], "last_name": r["last_name"],
                 "dni": r["dni"], "phone": r["phone"], "company_id": str(r["company_id"]) if r["company_id"] else None,
                 "company_name": r["company_name"]}
                for r in rows]
    finally:
        db.close()


@router.get("/available")
async def available_slots(day: date = Query(..., alias="date"), current_user: UserSchema = Depends(require_active_user)):
    if current_user.role not in ("admin", "secretary", "company", "patient"):
        raise HTTPException(status_code=403, detail="No tenés permiso para consultar turnos")
    if day.weekday() not in (2, 4):
        return {"date": day.isoformat(), "slots": []}
    db = _db()
    try:
        booked = db.execute(text("SELECT active_slot FROM appointments WHERE active_slot >= :start AND active_slot < :end"), {
            "start": datetime.combine(day, OPENING), "end": datetime.combine(day, time(12, 30)),
        }).scalars().all()
        booked_times = {value.strftime("%H:%M") for value in booked if value}
        slots = []
        cursor = datetime.combine(day, OPENING)
        final_start = datetime.combine(day, LAST_START)
        now_ar = datetime.now(ZoneInfo("America/Argentina/Buenos_Aires")).replace(tzinfo=None)
        while cursor <= final_start:
            label = cursor.strftime("%H:%M")
            if label not in booked_times and cursor > now_ar:
                slots.append(label)
            cursor += timedelta(minutes=SLOT_MINUTES)
        return {"date": day.isoformat(), "slots": slots}
    finally:
        db.close()


@router.get("")
async def list_appointments(
    start: date = Query(...), end: date = Query(...),
    current_user: UserSchema = Depends(require_active_user),
):
    if current_user.role not in ("admin", "secretary", "company", "patient"):
        raise HTTPException(status_code=403, detail="No tenés permiso para ver el calendario")
    if end < start or (end - start).days > 62:
        raise HTTPException(status_code=422, detail="El período del calendario no es válido")
    clauses = ["a.start_at >= :start_at", "a.start_at < :end_at"]
    params = {"start_at": datetime.combine(start, time.min), "end_at": datetime.combine(end + timedelta(days=1), time.min)}
    db = _db()
    try:
        if current_user.role == "patient":
            clauses.append("p.user_id = :uid")
            params["uid"] = current_user.id
        elif current_user.role == "company":
            company_id = _company_id(db, current_user.id)
            if not company_id:
                return []
            clauses.append("p.company_id = :cid")
            params["cid"] = company_id
        rows = db.execute(text(f"""
            SELECT a.id, a.patient_id, a.start_at, a.end_at, a.status, a.created_at,
                   p.first_name, p.last_name, p.dni, p.phone, p.user_id, p.company_id,
                   u.email, c.name AS company_name
            FROM appointments a
            JOIN patients p ON p.id = a.patient_id
            LEFT JOIN users u ON u.id = p.user_id
            LEFT JOIN companies c ON c.id = p.company_id
            WHERE {' AND '.join(clauses)}
            ORDER BY a.start_at
        """), params).mappings().all()
        return [_format(row) for row in rows]
    finally:
        db.close()


@router.post("")
async def create_appointment(payload: AppointmentCreate, current_user: UserSchema = Depends(require_active_user)):
    if current_user.role not in ("admin", "secretary", "company", "patient"):
        raise HTTPException(status_code=403, detail="No tenés permiso para reservar turnos")
    start_at = _slot_start(payload.date, payload.time)
    end_at = start_at + timedelta(minutes=SLOT_MINUTES)
    db = _db()
    appointment_id = str(uuid.uuid4())
    try:
        patient = db.execute(text("SELECT id, user_id, company_id FROM patients WHERE id = :pid FOR UPDATE"),
                             {"pid": payload.patient_id}).mappings().first()
        if not patient:
            raise HTTPException(status_code=404, detail="No se encontró el paciente seleccionado")
        if current_user.role == "patient" and patient["user_id"] != current_user.id:
            raise HTTPException(status_code=403, detail="Solo podés reservar para vos")
        if current_user.role == "company":
            company_id = _company_id(db, current_user.id)
            if not company_id or str(patient["company_id"]) != company_id:
                raise HTTPException(status_code=403, detail="Solo podés reservar para empleados de tu empresa")
        db.execute(text("""
            INSERT INTO appointments (id, patient_id, created_by_user_id, company_id, start_at, end_at, active_slot, status)
            VALUES (:id, :pid, :uid, :cid, :start_at, :end_at, :slot, 'booked')
        """), {"id": appointment_id, "pid": payload.patient_id, "uid": current_user.id,
               "cid": patient["company_id"], "start_at": start_at, "end_at": end_at, "slot": start_at})
        db.commit()
        return {"id": appointment_id, "patient_id": payload.patient_id, "start_at": start_at.isoformat(),
                "end_at": end_at.isoformat(), "status": "booked"}
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Ese horario ya fue reservado. Elegí otro turno disponible.")
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="No se pudo guardar el turno")
    finally:
        db.close()


@router.delete("/{appointment_id}")
async def cancel_appointment(appointment_id: str, current_user: UserSchema = Depends(require_active_user)):
    if current_user.role not in ("admin", "secretary", "company", "patient"):
        raise HTTPException(status_code=403, detail="No tenés permiso para cancelar turnos")
    db = _db()
    try:
        row = db.execute(text("""
            SELECT a.id, a.status, p.user_id, p.company_id
            FROM appointments a JOIN patients p ON p.id = a.patient_id
            WHERE a.id = :id FOR UPDATE
        """), {"id": appointment_id}).mappings().first()
        if not row:
            raise HTTPException(status_code=404, detail="No se encontró el turno")
        allowed = current_user.role in ("admin", "secretary")
        if current_user.role == "patient":
            allowed = row["user_id"] == current_user.id
        elif current_user.role == "company":
            allowed = bool(row["company_id"] and str(row["company_id"]) == _company_id(db, current_user.id))
        if not allowed:
            raise HTTPException(status_code=403, detail="No tenés permiso para cancelar este turno")
        if row["status"] == "cancelled":
            return {"id": appointment_id, "status": "cancelled"}
        db.execute(text("UPDATE appointments SET status = 'cancelled', active_slot = NULL WHERE id = :id"), {"id": appointment_id})
        db.commit()
        return {"id": appointment_id, "status": "cancelled"}
    except HTTPException:
        db.rollback()
        raise
    finally:
        db.close()
