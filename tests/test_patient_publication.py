"""Publication regressions using only an isolated in-memory database.

Run: python -m unittest discover -s tests -p test_patient_publication.py
"""
import unittest
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from auth.authentication import require_active_user
from routers import patients, studies, medical_records
from services.patient_access import studies_are_ready


class SQLiteSession(Session):
    def execute(self, statement, *args, **kwargs):
        # SQLite has no row locks; production uses MySQL's FOR UPDATE.
        return super().execute(text(str(statement).replace(" FOR UPDATE", "")), *args, **kwargs)


class PatientPublicationTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        with self.engine.begin() as db:
            for statement in (
                "CREATE TABLE companies (id TEXT, owner_user_id TEXT, name TEXT)",
                "CREATE TABLE users (id TEXT, is_active INTEGER)",
                "CREATE TABLE patients (id TEXT, company_id TEXT, user_id TEXT, patient_status TEXT, first_name TEXT, last_name TEXT, dni TEXT, date_of_birth TEXT, phone TEXT, address TEXT, social_security TEXT, study_type TEXT)",
                "CREATE TABLE studies (id TEXT, patient_id TEXT, study_type TEXT, status TEXT, created_by_user_id TEXT, created_at TEXT)",
                "CREATE TABLE study_files (id TEXT, study_id TEXT, is_report INTEGER, file_path TEXT, original_filename TEXT, mime_type TEXT, size_bytes INTEGER, uploaded_at TEXT)",
                "CREATE TABLE studies_admin (name TEXT, requires_report INTEGER)",
                "INSERT INTO companies VALUES ('company', 'owner', 'Empresa'), ('other-company', 'other-owner', 'Otra')",
                "INSERT INTO patients (id,company_id,user_id,patient_status) VALUES ('patient','company','patient-user','En proceso'), ('other','other-company','other-user','Completado')",
                "INSERT INTO studies_admin VALUES ('Audiometría',1), ('Opcional',0)",
                "INSERT INTO studies VALUES ('study','patient','Audiometría','Disponible','professional','2026-10-19')",
                "INSERT INTO study_files (id,study_id,is_report,file_path) VALUES ('file','study',0,'test.pdf'), ('report','study',1,'report.pdf')",
            ):
                db.execute(text(statement))
        self.app = FastAPI()
        for module in (patients, studies, medical_records):
            self.app.include_router(module.router)
            patcher = patch.object(module, "getConnectionForLogin", lambda: SQLiteSession(self.engine))
            patcher.start()
            self.addCleanup(patcher.stop)
        self.user = SimpleNamespace(id="owner", role="company", is_active=True)
        self.app.dependency_overrides[require_active_user] = lambda: self.user
        self.client = TestClient(self.app)
        self.files = tempfile.TemporaryDirectory()
        self.addCleanup(self.files.cleanup)
        Path(self.files.name, "test.pdf").write_bytes(b"%PDF-test")
        file_patcher = patch.object(studies, "STUDIES_DIR", self.files.name)
        file_patcher.start()
        self.addCleanup(file_patcher.stop)
        with self.engine.begin() as db:
            db.execute(text("UPDATE study_files SET file_path=:url WHERE id='file'"), {"url": f"{studies.DOMAIN_URL}/test.pdf"})
        self.addCleanup(self.client.close)
        self.addCleanup(self.engine.dispose)

    def sql(self, statement):
        with self.engine.begin() as db:
            db.execute(text(statement))

    def test_unpublished_patient_hidden_from_both_lists_and_details(self):
        self.assertEqual(self.client.get("/patients/").json()["patients"], [])
        self.assertEqual(self.client.get("/patients/getPatients").json(), [])
        for path in ("/patients/patient", "/studies/patient/patient", "/studies/study", "/studies/files/study", "/medical-records/patient/patient"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 404)

    def test_completed_employee_and_studies_are_visible(self):
        self.sql("UPDATE patients SET patient_status='Completado' WHERE id='patient'")
        self.assertEqual([p["id"] for p in self.client.get("/patients/").json()["patients"]], ["patient"])
        self.assertEqual([p["id"] for p in self.client.get("/patients/getPatients").json()], ["patient"])
        for path in ("/patients/patient", "/studies/patient/patient", "/studies/study", "/studies/files/study"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)
        self.assertEqual(self.client.get("/patients/other").status_code, 404)

    def test_completion_is_only_available_to_admin_and_secretary(self):
        for role in ("company", "professional", "patient"):
            self.user.role = role
            self.assertEqual(self.client.patch("/patients/patient/status", json={"patient_status": "Completado"}).status_code, 403)
        for role in ("admin", "secretary"):
            self.user.role = role
            self.assertEqual(self.client.patch("/patients/patient/status", json={"patient_status": "Completado"}).status_code, 200)

    def test_completion_rejected_for_missing_report_pending_or_no_studies(self):
        self.user.role = "secretary"
        for mutation in ("DELETE FROM study_files WHERE is_report=1", "UPDATE studies SET status='pending'", "DELETE FROM study_files", "DELETE FROM studies"):
            self.sql(mutation)
            response = self.client.patch("/patients/patient/status", json={"patient_status": "Completado"})
            self.assertEqual(response.status_code, 409)
            self.assertIn("administrador", response.json()["detail"])
        self.assertEqual(self.client.patch("/patients/patient/status", json={"patient_status": "En proceso"}).status_code, 200)

    def test_optional_report_and_consent_do_not_require_a_report(self):
        self.sql("DELETE FROM study_files WHERE is_report=1")
        with SQLiteSession(self.engine) as db:
            self.assertFalse(studies_are_ready(db, "patient"))
        for study_type in ("Opcional", "Consentimiento informado"):
            self.sql(f"UPDATE studies SET study_type='{study_type}'")
            with SQLiteSession(self.engine) as db:
                self.assertTrue(studies_are_ready(db, "patient"))

    def test_second_pending_study_prevents_publication(self):
        self.sql("INSERT INTO studies (id,patient_id,study_type,status) VALUES ('second','patient','Opcional','pending')")
        self.user.role = "secretary"
        self.assertEqual(self.client.patch("/patients/patient/status", json={"patient_status": "Completado"}).status_code, 409)

    def test_manual_completion_controls_visibility_even_when_incomplete(self):
        self.sql("UPDATE patients SET patient_status='Completado' WHERE id='patient'")
        self.sql("DELETE FROM study_files WHERE is_report=1")
        self.assertEqual(len(self.client.get("/patients/").json()["patients"]), 1)
        self.assertEqual(self.client.get("/studies/patient/patient").status_code, 200)
        self.sql("UPDATE patients SET patient_status='En proceso' WHERE id='patient'")
        self.assertEqual(self.client.get("/patients/patient").status_code, 404)

    def test_file_download_requires_approved_own_employee(self):
        path = "/studies/files/public/test.pdf"
        self.assertEqual(self.client.get(path).status_code, 404)
        self.sql("UPDATE patients SET patient_status='Completado' WHERE id='patient'")
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"%PDF-test")
        self.assertEqual(response.headers["cache-control"], "private, no-store")
        self.user.id = "other-owner"
        self.assertEqual(self.client.get(path).status_code, 404)
        self.app.dependency_overrides.clear()
        self.assertEqual(self.client.get(path).status_code, 401)

    def test_professional_sees_admin_approved_status_even_with_pending_studies(self):
        self.sql("UPDATE patients SET patient_status='Completado' WHERE id='patient'")
        self.user.role = "professional"
        row = next(p for p in self.client.get("/patients/getPatients").json() if p["id"] == "patient")
        self.assertEqual(row["patient_status"], "Completado")
        self.sql("UPDATE studies SET status='pending' WHERE id='study'")
        row = next(p for p in self.client.get("/patients/getPatients").json() if p["id"] == "patient")
        self.assertEqual(row["patient_status"], "Completado")

    def test_admin_can_publish_incomplete_employee_and_existing_files(self):
        self.sql("DELETE FROM study_files WHERE is_report=1")
        self.sql("UPDATE studies SET status='pending'")
        self.user.role = "admin"
        self.assertEqual(self.client.patch("/patients/patient/status", json={"patient_status": "Completado"}).status_code, 200)
        self.user.role = "company"
        self.assertEqual(len(self.client.get("/patients/").json()["patients"]), 1)
        self.assertEqual(len(self.client.get("/patients/getPatients").json()), 1)
        self.assertEqual(self.client.get("/patients/patient").status_code, 200)
        self.assertEqual(self.client.get("/studies/patient/patient").status_code, 200)
        self.assertEqual(self.client.get("/studies/files/public/test.pdf").status_code, 200)

    def test_admin_can_complete_employee_without_studies(self):
        self.sql("DELETE FROM studies")
        self.user.role = "admin"
        self.assertEqual(self.client.patch("/patients/patient/status", json={"patient_status": "Completado"}).status_code, 200)
        self.user.role = "company"
        self.assertEqual(len(self.client.get("/patients/").json()["patients"]), 1)

    def test_clinic_staff_can_read_in_progress_studies(self):
        for role in ("professional", "secretary", "admin"):
            self.user.role = role
            self.assertEqual(self.client.get("/studies/patient/patient").status_code, 200)

    def test_unauthenticated_studies_are_denied(self):
        self.app.dependency_overrides.clear()
        self.assertEqual(self.client.get("/studies/patient/patient").status_code, 401)

    def test_only_admin_and_secretary_can_delete_studies_or_files(self):
        for role in ("company", "professional", "patient"):
            self.user.role = role
            for path in ("/studies/study", "/studies/study/files/file", "/studies/study/files/report"):
                self.assertEqual(self.client.delete(path).status_code, 403)

    def test_admin_and_secretary_can_delete_report_without_removing_study(self):
        for role in ("admin", "secretary"):
            self.user.role = role
            self.sql(f"INSERT INTO study_files (id,study_id,is_report,file_path) VALUES ('report-{role}','study',1,'report.pdf')")
            self.assertEqual(self.client.delete(f"/studies/study/files/report-{role}").status_code, 200)
            with SQLiteSession(self.engine) as db:
                self.assertEqual(db.execute(text("SELECT COUNT(*) FROM studies WHERE id='study'")).scalar(), 1)
                self.assertEqual(db.execute(text("SELECT COUNT(*) FROM study_files WHERE id='file'")).scalar(), 1)

    def test_admin_and_secretary_can_delete_study_with_all_files(self):
        for role in ("admin", "secretary"):
            self.user.role = role
            self.sql(f"INSERT INTO studies (id,patient_id,study_type,status) VALUES ('{role}-study','patient','Opcional','pending')")
            self.sql(f"INSERT INTO study_files (id,study_id,is_report,file_path) VALUES ('{role}-file','{role}-study',0,'{role}.pdf')")
            Path(self.files.name, f"{role}.pdf").write_bytes(b"%PDF-test")
            self.assertEqual(self.client.delete(f"/studies/{role}-study").status_code, 200)
            with SQLiteSession(self.engine) as db:
                self.assertEqual(db.execute(text("SELECT COUNT(*) FROM studies WHERE id=:id"), {"id": f"{role}-study"}).scalar(), 0)
                self.assertEqual(db.execute(text("SELECT COUNT(*) FROM study_files WHERE study_id=:id"), {"id": f"{role}-study"}).scalar(), 0)
            self.assertFalse(Path(self.files.name, f"{role}.pdf").exists())

    def test_file_cannot_be_deleted_through_a_different_study(self):
        self.user.role = "admin"
        self.assertEqual(self.client.delete("/studies/other-study/files/file").status_code, 404)
        self.assertTrue(Path(self.files.name, "test.pdf").exists())


if __name__ == "__main__":
    unittest.main()
