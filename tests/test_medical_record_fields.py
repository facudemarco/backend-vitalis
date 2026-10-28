import unittest
from decimal import Decimal

from pydantic import ValidationError
from models.medical_record import MedicalRecordData, MedicalRecordClinicalExamInput as MedicalRecordClinicalExam, MedicalRecordFullResponse


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

    def test_age_accepts_year_suffix_and_stores_only_the_number(self):
        for raw, expected in (("28 años", "28"),("1 año", "1"),("150 AÑOS", "150"),("28años", "28"),(" 28 años ", "28")):
            with self.subTest(value=raw):
                self.assertEqual(MedicalRecordData(age=raw).age, expected)

    def test_age_rejects_invalid_values_and_numeric_payloads(self):
        for value in ("0", "151", "999", "01", "1.5", "-1", "+2", "1e2", "abc", "151 años", "28 meses", "28.5 años", "0 años", "01 años", 35):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                MedicalRecordData(age=value)

    def test_legacy_or_empty_age_is_unset(self):
        self.assertIsNone(MedicalRecordData().age)
        self.assertIsNone(MedicalRecordData(age="").age)


class ClinicalMeasurementTests(unittest.TestCase):
    def test_units_and_comma_decimals_normalize_to_canonical_numbers(self):
        record = MedicalRecordClinicalExam(talla="175cm", peso="80 KG", saturacion="99%", imc="20,15", ta_min="80mmhg", ta_max="120 mmHg")
        self.assertEqual(record.model_dump(exclude_none=True), {"talla":175.0,"peso":80.0,"saturacion":99.0,"imc":20.15,"ta_min":80.0,"ta_max":120.0})

    def test_imc_accepts_integer_one_or_two_decimals(self):
        for value in (20, 20.1, 20.15, "20", "20,1", "20.15"):
            self.assertEqual(MedicalRecordClinicalExam(imc=value).imc, float(str(value).replace(",", ".")))

    def test_wrong_units_invalid_numbers_and_excess_imc_precision_are_rejected(self):
        for key,value in (("talla","175kg"),("peso","80cm"),("saturacion","99kg"),("imc","20.123"),("imc","20kg"),("ta_min","80cm"),("ta_max","120/80"),("peso",float("nan")),("peso",True),("peso",-1)):
            with self.subTest(field=key,value=value), self.assertRaises(ValidationError):
                MedicalRecordClinicalExam(**{key:value})

    def test_blank_measurements_and_existing_numbers_remain_compatible(self):
        self.assertIsNone(MedicalRecordClinicalExam(peso=" ").peso)
        self.assertEqual(MedicalRecordClinicalExam(talla=175,peso=80.5).peso,80.5)
        self.assertEqual(MedicalRecordClinicalExam(imc=Decimal("20.1500")).imc,20.15)

    def test_legacy_bmi_with_more_decimals_remains_readable(self):
        record=MedicalRecordFullResponse.model_validate({"id":"legacy", "patient_id":"patient", "medical_record_clinical_exam":{"imc":20.123}})
        self.assertEqual(record.medical_record_clinical_exam.imc,20.123)
