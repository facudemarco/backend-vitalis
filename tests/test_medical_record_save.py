"""Real HTTP create/update regressions with a disposable SQLite database."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from auth.authentication import require_active_user
from routers import medical_records
from services import medical_record_validation as validation


class MedicalRecordSaveTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        with self.engine.begin() as db:
            db.execute(text("CREATE TABLE patients (id TEXT PRIMARY KEY, company_id TEXT)"))
            db.execute(text("INSERT INTO patients VALUES ('patient', NULL)"))
            db.execute(text("CREATE TABLE medical_record (id TEXT PRIMARY KEY, patient_id TEXT)"))
            db.execute(text("CREATE TABLE medical_record_data (id TEXT PRIMARY KEY, medical_record_id TEXT, complete_name TEXT, company_name TEXT, phone INTEGER, education_level TEXT, sector TEXT, age TEXT)"))
        self.schema_missing = False
        self.phone_bigint = True
        self.files = tempfile.TemporaryDirectory()
        self.addCleanup(self.files.cleanup)
        self.addCleanup(self.engine.dispose)
        for target, value in (
            ("getConnectionForLogin", lambda: Session(self.engine)),
            ("SIGNATURES_DIR", Path(self.files.name)),
            ("DATA_IMAGES_DIR", Path(self.files.name)),
        ):
            patcher = patch.object(medical_records, target, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        def schema(_db, table):
            # Model the MySQL metadata for the otherwise real SQLite tables.
            columns = []
            for col in inspect(_db.connection()).get_columns(table):
                name = col["name"]
                if self.schema_missing and name in ("education_level", "sector"):
                    continue
                numeric = name == "phone"
                columns.append({"COLUMN_NAME": name, "COLUMN_TYPE": "bigint" if self.phone_bigint else "int(11)",
                    "DATA_TYPE": ("bigint" if self.phone_bigint else "int") if numeric else "varchar",
                    "IS_NULLABLE": "NO" if name == "id" else "YES", "COLUMN_DEFAULT": None, "EXTRA": "",
                    "CHARACTER_MAXIMUM_LENGTH": None if numeric else 255})
            return columns
        patcher = patch.object(validation, "get_section_schema", schema)
        patcher.start()
        self.addCleanup(patcher.stop)
        app = FastAPI()
        app.include_router(medical_records.router)
        app.dependency_overrides[require_active_user] = lambda: SimpleNamespace(id="admin", role="admin", is_active=True)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def save(self, data, record_id=None, image=False):
        payload = {"patient_id": "patient", "data": json.dumps({"medical_record_data": data})}
        files = {"data_img": ("test.png", b"fake-image", "image/png")} if image else None
        return self.client.request("PUT" if record_id else "POST", f"/medical-records/{record_id or ''}", data=payload, files=files)

    def test_create_with_empty_education_and_large_phone_succeeds(self):
        response = self.save({"education_level": "", "sector": "Mecánica", "phone": 2475425992})
        self.assertEqual(response.status_code, 200, response.text)
        with self.engine.connect() as db:
            row = db.execute(text("SELECT phone,education_level,sector FROM medical_record_data")).mappings().one()
        self.assertEqual(row["phone"], 2475425992)
        self.assertIsNone(row["education_level"])
        self.assertEqual(row["sector"], "Mecánica")

    def test_update_can_clear_education_and_preserve_large_phone(self):
        created = self.save({"education_level": "Terciarios", "phone": 2475425992})
        response = self.save({"education_level": "", "phone": 2475425992}, record_id=created.json()["id"])
        self.assertEqual(response.status_code, 200, response.text)
        with self.engine.connect() as db:
            self.assertIsNone(db.execute(text("SELECT education_level FROM medical_record_data")).scalar())

    def test_missing_columns_fail_before_parent_or_image_is_written(self):
        self.schema_missing = True
        with self.assertLogs(validation.logger, level="ERROR"):
            response = self.save({"education_level": None, "sector": "Prueba"}, image=True)
        self.assertEqual(response.status_code, 503, response.text)
        self.assertEqual(response.json()["detail"]["code"], "medical_record_schema_outdated")
        with self.engine.connect() as db:
            self.assertEqual(db.execute(text("SELECT COUNT(*) FROM medical_record")).scalar(), 0)
        self.assertEqual(list(Path(self.files.name).iterdir()), [])

    def test_int_phone_overflow_is_detected_before_insert(self):
        self.phone_bigint = False
        with self.assertLogs(validation.logger, level="ERROR"):
            response = self.save({"phone": 2475425992})
        self.assertEqual(response.status_code, 503, response.text)
        self.assertEqual(response.json()["detail"]["code"], "medical_record_schema_outdated")

    def test_failed_update_preserves_saved_data(self):
        created = self.save({"complete_name": "Nombre previo", "education_level": "Primarios"})
        self.schema_missing = True
        with self.assertLogs(validation.logger, level="ERROR"):
            response = self.save({"complete_name": "Otro nombre", "education_level": "Secundarios"}, record_id=created.json()["id"])
        self.assertEqual(response.status_code, 503)
        with self.engine.connect() as db:
            self.assertEqual(db.execute(text("SELECT complete_name FROM medical_record_data")).scalar(), "Nombre previo")

    def test_invalid_education_is_still_a_validation_error(self):
        self.assertEqual(self.save({"education_level": "Otra opción"}).status_code, 422)

    def test_age_persists_as_text_on_create_and_update(self):
        response = self.save({"age": "35"})
        self.assertEqual(response.status_code, 200, response.text)
        updated = self.save({"age": "150"}, record_id=response.json()["id"])
        self.assertEqual(updated.status_code, 200, updated.text)
        with self.engine.connect() as db:
            row = db.execute(text("SELECT age FROM medical_record_data")).scalar()
        self.assertEqual(row, "150")

    def test_out_of_range_age_cannot_create_a_record(self):
        self.assertEqual(self.save({"age": "151"}).status_code, 422)
        with self.engine.connect() as db:
            self.assertEqual(db.execute(text("SELECT COUNT(*) FROM medical_record")).scalar(), 0)
