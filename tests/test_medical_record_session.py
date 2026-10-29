"""Six-hour work sessions; no production database or real credentials."""
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from auth.authentication import (require_active_user, create_access_token, verify_token,
    ACCESS_TOKEN_EXPIRE_MINUTES, SECRET_KEY, ALGORITHM)
from routers import login


class MedicalRecordSessionTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        with self.engine.begin() as db:
            db.execute(text("CREATE TABLE patients (id TEXT, user_id TEXT, company_id TEXT, patient_status TEXT)"))
            db.execute(text("INSERT INTO patients VALUES ('patient', 'patient-user', NULL, 'En proceso')"))
        self.user = SimpleNamespace(id="editor", role="professional", is_active=True)
        for name, value in (
            ("getConnectionForLogin", lambda: Session(self.engine)),
            ("authenticate_user", lambda email, password: self.user if email == "qa@example.invalid" and password == "test-only" else None),
        ):
            mocked = patch.object(login, name, value); mocked.start(); self.addCleanup(mocked.stop)
        app = FastAPI(); app.include_router(login.router)
        app.dependency_overrides[require_active_user] = lambda: self.user
        self.client = TestClient(app)
        self.addCleanup(self.client.close); self.addCleanup(self.engine.dispose)

    def test_login_tokens_have_six_hours_and_issued_at(self):
        self.assertEqual(ACCESS_TOKEN_EXPIRE_MINUTES, 360)
        token = create_access_token({"id": "editor", "role": "professional"})
        payload = verify_token(token)
        self.assertEqual(payload["exp"] - payload["iat"], 21600)

    def test_opening_a_patient_starts_a_fresh_six_hour_window(self):
        response = self.client.post("/medical-session/patient")
        self.assertEqual(response.status_code, 200, response.text)
        remaining = response.json()["expires_at"] - datetime.now(timezone.utc).timestamp()
        self.assertTrue(21590 < remaining <= 21600)
        self.assertEqual(response.json()["user_id"], "editor")
        cookie = response.headers["set-cookie"]
        for attribute in ("HttpOnly", "Secure", "Max-Age=21600", "Path=/"):
            self.assertIn(attribute, cookie)

    def test_normal_login_cookie_also_matches_the_six_hour_token(self):
        with patch.object(login, "resolve_profile_ids", return_value={}), patch.object(login, "build_token_payload", return_value={"id":"editor","role":"professional"}):
            response = self.client.post("/login", data={"email":"qa@example.invalid","password":"test-only"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn("Max-Age=21600", response.headers["set-cookie"])
        payload = verify_token(response.json()["access_token"])
        self.assertEqual(payload["exp"] - payload["iat"], 21600)

    def test_patient_access_and_editor_role_are_checked_before_renewal(self):
        self.assertEqual(self.client.post("/medical-session/missing").status_code, 404)
        for role in ("company", "patient", "secretary"):
            self.user.role = role
            response = self.client.post("/medical-session/patient")
            self.assertEqual(response.status_code, 403)
            self.assertNotIn("set-cookie", response.headers)
        self.user.role = "professional"; self.user.is_active = False
        self.assertEqual(self.client.post("/medical-session/patient").status_code, 403)

    def test_other_account_cannot_replace_an_open_ficha_session(self):
        response = self.client.post("/medical-session/patient", data={"expected_user_id": "another-editor"})
        self.assertEqual(response.status_code, 409)
        self.assertNotIn("set-cookie", response.headers)
        response = self.client.post("/medical-session/patient/reauthenticate", data={
            "email": "qa@example.invalid", "password": "test-only", "expected_user_id": "another-editor"})
        self.assertEqual(response.status_code, 409)
        self.assertNotIn("set-cookie", response.headers)

    def test_expired_session_can_reauthenticate_without_changing_account(self):
        rejected = self.client.post("/medical-session/patient/reauthenticate", data={"email": "qa@example.invalid", "password": "wrong"})
        self.assertEqual(rejected.status_code, 401)
        self.assertNotIn("set-cookie", rejected.headers)
        response = self.client.post("/medical-session/patient/reauthenticate", data={
            "email": "qa@example.invalid", "password": "test-only", "expected_user_id": "editor"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["user_id"], "editor")

    def test_expired_signed_token_is_rejected_and_verify_reports_false(self):
        token = jwt.encode({"id": "editor", "role": "professional", "exp": datetime.now(timezone.utc) - timedelta(seconds=1)}, SECRET_KEY, algorithm=ALGORITHM)
        with self.assertRaises(HTTPException): verify_token(token)
        self.client.cookies.set("Authorization", "Bearer " + token)
        response = self.client.get("/verify-token")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["valid"])
