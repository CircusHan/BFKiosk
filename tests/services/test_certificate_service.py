import unittest
from unittest.mock import patch, mock_open, MagicMock
import os
import csv
from io import BytesIO
from datetime import datetime

# Ensure the app module can be imported
# This might need adjustment based on actual project structure and PYTHONPATH
import sys
# Ensure the app package is importable during test collection
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.services.certificate_service import (
    get_prescription_data_for_pdf,
    prepare_prescription_pdf,
    prepare_medical_confirmation_pdf,
    MissingKoreanFontError # Assuming this is also in certificate_service or utils
)
# If MissingKoreanFontError is in utils, the import path needs to be correct.
# For now, assuming it's accessible or defined in certificate_service for simplicity of this example.

# If create_prescription_pdf_bytes and create_confirmation_pdf_bytes are in utils:
# from app.utils.pdf_generator import create_prescription_pdf_bytes, create_confirmation_pdf_bytes
# And then they would be patched like: @patch('app.services.certificate_service.create_prescription_pdf_bytes')

# Mock data for a test CSV
MOCK_CSV_DATA_PRESCRIPTIONS = """name,code,unit_dose,daily_frequency,total_days
MedA,A001,1,3,5
MedB,B002,2,2,7
MedC,C003,1,1,3
"""

MOCK_CSV_DATA_DEPARTMENT_SPECIFIC = """name,code,unit_dose,daily_frequency,total_days
DeptMedX,X001,1,3,5
DeptMedY,Y002,2,2,7
"""


class TestCertificateService(unittest.TestCase):

    def setUp(self):
        # Basic patient info
        self.patient_name = "홍길동"
        self.patient_rrn = "900101-1234567"
        self.department = "내과"

    @patch('app.services.certificate_service.os.path.exists')
    @patch('builtins.open', new_callable=mock_open)
    def test_get_prescription_data_for_pdf_success_department_csv_exists(self, mock_file_open, mock_path_exists):
        # Scenario: Department-specific CSV exists and is used.
        mock_path_exists.side_effect = lambda path: path.endswith(f"prescriptions_{self.department.lower()}.csv") # Only dept CSV exists
        mock_file_open.return_value.read.return_value = MOCK_CSV_DATA_DEPARTMENT_SPECIFIC

        # Simulate that the department CSV is found and read
        mock_csv_file = mock_open(read_data=MOCK_CSV_DATA_DEPARTMENT_SPECIFIC)
        mock_file_open.side_effect = [mock_csv_file.return_value]

        last_prescriptions = ["DeptMedX", "DeptMedY"]
        last_total_fee = 15000

        result = get_prescription_data_for_pdf(self.department, last_prescriptions, last_total_fee)

        self.assertIsNotNone(result)
        self.assertEqual(result["department"], self.department)
        self.assertEqual(len(result["prescriptions"]), 2)
        self.assertEqual(result["prescriptions"][0]["name"], "DeptMedX")
        self.assertEqual(result["total_fee"], last_total_fee)
        mock_path_exists.assert_any_call(os.path.join("app", "data", f"prescriptions_{self.department.lower()}.csv"))
        # open should be called once for the department specific file
        self.assertEqual(mock_file_open.call_count, 1)


    @patch('app.services.certificate_service.os.path.exists')
    @patch('builtins.open', new_callable=mock_open)
    def test_get_prescription_data_for_pdf_fallback_to_generic_csv(self, mock_file_open, mock_path_exists):
        # Scenario: Department-specific CSV does NOT exist, falls back to generic.
        mock_path_exists.side_effect = lambda path: path.endswith("prescriptions.csv") # Only generic CSV exists

        mock_csv_file = mock_open(read_data=MOCK_CSV_DATA_PRESCRIPTIONS)
        mock_file_open.side_effect = [mock_csv_file.return_value]

        last_prescriptions = ["MedA", "MedB"]
        last_total_fee = 12000

        result = get_prescription_data_for_pdf(self.department, last_prescriptions, last_total_fee)

        self.assertIsNotNone(result)
        self.assertEqual(len(result["prescriptions"]), 2)
        self.assertEqual(result["prescriptions"][0]["name"], "MedA")
        mock_path_exists.assert_any_call(os.path.join("app", "data", f"prescriptions_{self.department.lower()}.csv"))
        mock_path_exists.assert_any_call(os.path.join("app", "data", "prescriptions.csv"))
        self.assertEqual(mock_file_open.call_count, 1) # Called once for the generic file


    @patch('app.services.certificate_service.os.path.exists', return_value=False)
    def test_get_prescription_data_for_pdf_no_csv_found(self, mock_path_exists):
        # Scenario: Neither department-specific nor generic CSV exists.
        last_prescriptions = ["MedA"]
        last_total_fee = 5000
        result = get_prescription_data_for_pdf(self.department, last_prescriptions, last_total_fee)
        self.assertIsNone(result)

    def test_get_prescription_data_for_pdf_no_last_prescriptions(self):
        # Scenario: last_prescriptions is empty
        result = get_prescription_data_for_pdf(self.department, [], 0)
        self.assertIsNone(result) # Original logic returns None if last_prescriptions is empty

    @patch('app.services.certificate_service.os.path.exists')
    @patch('builtins.open', new_callable=mock_open)
    def test_get_prescription_data_for_pdf_prescriptions_not_in_file(self, mock_file_open, mock_path_exists):
        mock_path_exists.return_value = True # Assume generic prescriptions.csv exists
        mock_csv_file = mock_open(read_data=MOCK_CSV_DATA_PRESCRIPTIONS)
        mock_file_open.return_value = mock_csv_file.return_value

        last_prescriptions = ["MedD", "MedE"] # These are not in MOCK_CSV_DATA_PRESCRIPTIONS
        last_total_fee = 3000

        result = get_prescription_data_for_pdf(self.department, last_prescriptions, last_total_fee)
        self.assertIsNotNone(result)
        self.assertEqual(len(result["prescriptions"]), 2)
        self.assertEqual(result["prescriptions"][0]["name"], "MedD")
        self.assertEqual(result["prescriptions"][0]["code"], "N/A") # Check placeholder for not found items


    @patch('app.services.certificate_service.create_prescription_pdf_bytes', return_value=BytesIO(b"fake_pdf_content"))
    def test_prepare_prescription_pdf_success(self, mock_create_pdf):
        prescription_details = {
            "doctor_name": "김의사",
            "doctor_license_number": "12345",
            "department": self.department,
            "prescriptions": [{"name": "MedA", "code": "A001", "unit_dose": "1", "daily_frequency": "3", "total_days": "5"}],
            "total_fee": 7500,
            "issue_date": "2023-10-01"
        }

        pdf_bytes, filename = prepare_prescription_pdf(self.patient_name, self.patient_rrn, self.department, prescription_details)

        self.assertIsNotNone(pdf_bytes)
        self.assertEqual(pdf_bytes.getvalue(), b"fake_pdf_content")
        self.assertTrue(filename.startswith(f"prescription_{self.patient_name}_"))
        self.assertTrue(filename.endswith(".pdf"))

        expected_call_data = prescription_details.copy()
        expected_call_data["patient_name"] = self.patient_name
        expected_call_data["patient_rrn"] = self.patient_rrn
        mock_create_pdf.assert_called_once_with(expected_call_data)

    def test_prepare_prescription_pdf_no_details(self):
        pdf_bytes, filename = prepare_prescription_pdf(self.patient_name, self.patient_rrn, self.department, None)
        self.assertIsNone(pdf_bytes)
        self.assertIsNone(filename)

    @patch('app.services.certificate_service.create_confirmation_pdf_bytes', return_value=BytesIO(b"fake_confirm_pdf"))
    @patch('app.services.certificate_service.random.randint', return_value=7) # Mock random days for diagnosis date
    def test_prepare_medical_confirmation_pdf_success(self, mock_randint, mock_create_confirm_pdf):
        disease_name = "감기" # Department used as disease_name

        pdf_bytes, filename = prepare_medical_confirmation_pdf(self.patient_name, self.patient_rrn, disease_name)

        self.assertIsNotNone(pdf_bytes)
        self.assertEqual(pdf_bytes.getvalue(), b"fake_confirm_pdf")
        self.assertTrue(filename.startswith(f"medical_confirmation_{self.patient_name}_"))
        self.assertTrue(filename.endswith(".pdf"))

        # Check if create_confirmation_pdf_bytes was called with correct arguments
        # Need to be careful about date_of_diagnosis and date_of_issue as they are generated inside
        args, kwargs = mock_create_confirm_pdf.call_args
        self.assertEqual(kwargs["patient_name"], self.patient_name)
        self.assertEqual(kwargs["patient_rrn"], self.patient_rrn)
        self.assertEqual(kwargs["disease_name"], disease_name)
        self.assertTrue("date_of_diagnosis" in kwargs)
        self.assertTrue("date_of_issue" in kwargs)
        self.assertEqual(kwargs["date_of_issue"], datetime.now().strftime("%Y-%m-%d"))


if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
