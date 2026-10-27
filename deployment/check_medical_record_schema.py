"""Run manually: python -m deployment.check_medical_record_schema (read-only)."""
import json
from typing import get_args

from sqlalchemy import text
from Database.getConnection import engine
from models.medical_record import MedicalRecordFullRequest


def main():
    with engine.connect() as conn:
        conn.exec_driver_sql("START TRANSACTION READ ONLY")
        rows = conn.execute(text("""
            SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME LIKE 'medical_record%'
        """)).mappings().all()
        conn.rollback()
    tables = {}
    for row in rows:
        tables.setdefault(row["TABLE_NAME"], {})[row["COLUMN_NAME"]] = row["DATA_TYPE"]
    missing = {}
    for table, field in MedicalRecordFullRequest.model_fields.items():
        model = next((t for t in [field.annotation, *get_args(field.annotation)] if hasattr(t, "model_fields")), None)
        if model:
            absent = sorted(set(model.model_fields) - set(tables.get(table, {})))
            if absent:
                missing[table] = absent
    phone_ready = tables.get("medical_record_data", {}).get("phone") == "bigint"
    ok = not missing and phone_ready
    print(json.dumps({"ready": ok, "missing_columns": missing, "phone_bigint": phone_ready}))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
