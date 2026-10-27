import unittest

from pydantic import ValidationError
from models.medical_record import MedicalRecordData


class MedicalRecordFieldsTests(unittest.TestCase):
    def test_education_options_and_sector_survive_serialization(self):
        for level in ("Primarios", "Secundarios", "Terciarios"):
            with self.subTest(level=level):
                record = MedicalRecordData(company_name="Empresa de prueba", education_level=level, sector="Producción")
                reloaded = MedicalRecordData.model_validate_json(record.model_dump_json())
                self.assertEqual(reloaded.education_level, level)
                self.assertEqual(reloaded.sector, "Producción")
                self.assertEqual(reloaded.company_name, "Empresa de prueba")

    def test_invalid_education_is_rejected(self):
        for level in ("Universitarios", "primarios"):
            with self.subTest(level=level), self.assertRaises(ValidationError):
                MedicalRecordData(education_level=level)

    def test_old_records_can_still_be_read(self):
        record = MedicalRecordData(complete_name="Paciente de prueba")
        self.assertIsNone(record.education_level)
        self.assertIsNone(record.sector)
        self.assertNotIn("education_level", record.model_dump(exclude_unset=True))

    def test_education_can_be_omitted_or_cleared(self):
        for value in (None, "", "  "):
            self.assertIsNone(MedicalRecordData(education_level=value).education_level)

    def test_sector_length_is_bounded(self):
        MedicalRecordData(sector="x" * 255)
        with self.assertRaises(ValidationError):
            MedicalRecordData(sector="x" * 256)

    def test_age_is_a_string_between_one_and_150(self):
        for value in ("1", "35", "99", "100", "149", "150"):
            with self.subTest(value=value):
                record = MedicalRecordData(age=value)
                self.assertEqual(record.age, value)
                self.assertIsInstance(record.model_dump()["age"], str)

    def test_age_rejects_invalid_values_and_numeric_payloads(self):
        for value in ("0", "151", "999", "01", "1.5", "-1", "+2", "1e2", "abc", " 2", "2 ", 35):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                MedicalRecordData(age=value)

    def test_legacy_or_empty_age_is_unset(self):
        self.assertIsNone(MedicalRecordData().age)
        self.assertIsNone(MedicalRecordData(age="").age)
