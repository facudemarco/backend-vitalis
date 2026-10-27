"""Check submitted sections against database metadata before writing files or rows."""
import logging

from fastapi import HTTPException
from sqlalchemy import text

logger = logging.getLogger(__name__)
LABELS = {"phone": "Teléfono", "education_level": "Estudios", "sector": "Sector", "sons": "Cantidad de hijos", "age": "Edad"}


def get_section_schema(db, table):
    cache = db.info.setdefault("medical_record_schema", {})
    if table not in cache:
        cache[table] = db.execute(text("""
            SELECT COLUMN_NAME, COLUMN_TYPE, DATA_TYPE, IS_NULLABLE,
                   COLUMN_DEFAULT, EXTRA, CHARACTER_MAXIMUM_LENGTH
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :table_name
        """), {"table_name": table}).mappings().all()
    return cache[table]


def schema_error(table, fields):
    logger.error("medical_record_schema_outdated table=%s fields=%s", table, ",".join(fields))
    return HTTPException(status_code=503, detail={
        "code": "medical_record_schema_outdated",
        "message": "La base de datos necesita una actualización para guardar la ficha. Contactá a administración; no es necesario volver a completar los datos.",
    })


def validate_section_data(db, table, data, check_required=True):
    columns = {col["COLUMN_NAME"]: col for col in get_section_schema(db, table)}
    absent = sorted(set(data) - set(columns))
    if absent:
        raise schema_error(table, absent)
    problems = []
    for name, col in columns.items():
        value = data.get(name)
        label = LABELS.get(name, name.replace("_", " ").capitalize())
        if (check_required and col["IS_NULLABLE"] == "NO" and col["COLUMN_DEFAULT"] is None
                and "auto_increment" not in (col["EXTRA"] or "")
                and (value is None or isinstance(value, str) and not value.strip())):
            problems.append({"field": name, "label": label, "message": f"Completá el campo {label}."})
        if value is None:
            continue
        bits = {"tinyint": 8, "smallint": 16, "mediumint": 24, "int": 32, "bigint": 64}.get(col["DATA_TYPE"])
        if bits and isinstance(value, int):
            unsigned = "unsigned" in col["COLUMN_TYPE"].lower()
            low, high = (0, 2 ** bits - 1) if unsigned else (-2 ** (bits - 1), 2 ** (bits - 1) - 1)
            if not low <= value <= high:
                if name == "phone":
                    raise schema_error(table, ["phone: requiere BIGINT para teléfonos completos"])
                problems.append({"field": name, "label": label, "message": f"El valor de {label} supera el rango admitido."})
        limit = col.get("CHARACTER_MAXIMUM_LENGTH")
        if isinstance(value, str) and limit is not None and len(value) > limit:
            problems.append({"field": name, "label": label, "message": f"{label} admite hasta {limit} caracteres."})
    if problems:
        raise HTTPException(status_code=422, detail={"message": "Revisá los datos de la ficha.", "fields": problems})


def preflight_medical_record(db, payload):
    for table, data in payload.items():
        if table.startswith("medical_record_") and isinstance(data, dict) and data:
            validate_section_data(db, table, data, check_required=False)


def database_save_error(exc, operation):
    # SQLAlchemy exception strings may contain all submitted clinical data. Never log them.
    args = getattr(getattr(exc, "orig", None), "args", ())
    errno = args[0] if args and isinstance(args[0], int) else None
    logger.error("medical_record_save_failed operation=%s exception=%s db_errno=%s", operation, type(exc).__name__, errno)
    if errno in (1054, 1146, 1264):
        return schema_error("medical_record", [f"database_error_{errno}"])
    return HTTPException(status_code=500, detail={
        "code": "medical_record_save_failed",
        "message": "No se pudo guardar la ficha por un problema del servidor. Reintentá o contactá a administración si continúa.",
    })
