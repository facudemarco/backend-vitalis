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
        for level in ("Universitarios", "", "primarios"):
            with self.subTest(level=level), self.assertRaises(ValidationError):
                MedicalRecordData(education_level=level)

    def test_old_records_can_still_be_read(self):
        record = MedicalRecordData(complete_name="Paciente de prueba")
        self.assertIsNone(record.education_level)
        self.assertIsNone(record.sector)
        self.assertNotIn("education_level", record.model_dump(exclude_unset=True))

    def test_sector_length_is_bounded(self):
        MedicalRecordData(sector="x" * 255)
        with self.assertRaises(ValidationError):
            MedicalRecordData(sector="x" * 256)
