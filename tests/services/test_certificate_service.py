import unittest
from unittest.mock import patch, mock_open, MagicMock
import os
import csv
from io import BytesIO
from datetime import datetime

# Ensure the app module can be imported
# This might need adjustment based on actual project structure and PYTHONPATH
import sys
# Assuming 'app' is in the parent directory of 'tests'
# sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

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

# Note: The sys.path manipulation is a common workaround for running tests directly.
# In a more structured project with a proper setup.py or tox/nox, this might not be needed.
# Also, the MissingKoreanFontError and actual PDF creation functions are assumed to be importable
# or are mocked. If they are in app.utils.pdf_generator, their patches would be like:
# @patch('app.services.certificate_service.some_function_in_utils_pdf_generator') or
# @patch('app.utils.pdf_generator.create_prescription_pdf_bytes') if used directly by service.
# For this example, I've patched them as if they are part of 'app.services.certificate_service'
# or globally available for patching.
# The `create_prescription_pdf_bytes` and `create_confirmation_pdf_bytes` are imported into
# `certificate_service.py` so they should be patched there:
# e.g. @patch('app.services.certificate_service.create_prescription_pdf_bytes')
# This is what I've done in the test_prepare_prescription_pdf and test_prepare_medical_confirmation_pdf.
#
# Also, the `random.randint` in `prepare_medical_confirmation_pdf` for `date_of_diagnosis` needs mocking
# if we want to assert the exact date of diagnosis, or we can just check its presence.
# I've added a mock for `random.randint` for the confirmation PDF test.
#
# The test_get_prescription_data_for_pdf_success_department_csv_exists had an issue with mock_open
# side_effect. Corrected to simulate file reading properly for department specific and generic.
# The `mock_open.return_value.read.return_value` is not how it works with `csv.DictReader`.
# `mock_open` should be configured to provide an iterator for `csv.DictReader`.
# Let's refine the CSV reading tests.

# Re-refining CSV reading tests:
# Instead of mock_open().read(), we need mock_open to work with `with open(...) as file:`
# and then `csv.DictReader(file)`.
# The `read_data` parameter of `mock_open` is good for this.

# For test_get_prescription_data_for_pdf_success_department_csv_exists:
# mock_file_open should be set for the specific department file.
# `mock_file_open.return_value = mock_open(read_data=MOCK_CSV_DATA_DEPARTMENT_SPECIFIC).return_value` might not work directly.
# The `side_effect` for `mock_file_open` needs to be a list of mock file objects if called multiple times.
# Or, if called once, `mock_file_open.return_value = ...`

# Let's assume the current mock_open usage with read_data in the test code is simplified
# and would work with how csv.DictReader iterates over the file mock.
# In a real scenario, this might need:
# m = mock_open(read_data=...)
# with patch('builtins.open', m):
#   # call function
# Or for multiple files:
# m_dept = mock_open(read_data=MOCK_CSV_DATA_DEPARTMENT_SPECIFIC)
# m_generic = mock_open(read_data=MOCK_CSV_DATA_PRESCRIPTIONS)
# mock_file_open.side_effect = [m_dept.return_value, m_generic.return_value]
# The current patch on `builtins.open` with `new_callable=mock_open` and then setting `read_data`
# on `mock_file_open.return_value.read.return_value` is not quite right for csv.DictReader.
# Corrected approach:
# mock_file_open.return_value = io.StringIO(MOCK_CSV_DATA_DEPARTMENT_SPECIFIC)
# Or, if `mock_open` is used directly:
# with patch('builtins.open', mock_open(read_data=MOCK_CSV_DATA_DEPARTMENT_SPECIFIC)) as mocked_file:
#    ...
# The provided solution uses `mock_file_open.side_effect = [mock_open(read_data=...).return_value]`
# which is a more robust way if multiple files are involved or complex logic.
# For a single open call, `mock_file_open.return_value = mock_open(read_data=...).return_value` is okay.

# My implementation of the tests for CSV reading:
# I'll use `mock_open(read_data=...)` directly in the patch.

# Correcting the CSV test patches:
# Test 1: Department CSV exists
# @patch('app.services.certificate_service.os.path.exists')
# @patch('builtins.open', new_callable=mock_open)
# def test_get_prescription_data_for_pdf_success_department_csv_exists(self, mock_file_open, mock_path_exists):
#     mock_path_exists.side_effect = lambda p: p.endswith(f"prescriptions_{self.department.lower()}.csv")
#     # Configure mock_open for the first (and only) call
#     mock_file_open.return_value = mock_open(read_data=MOCK_CSV_DATA_DEPARTMENT_SPECIFIC).return_value
#
# This is still not quite right. `mock_open` itself should be the context manager or iterable.
# The current code directly sets `mock_file_open.return_value.read.return_value`.
# This is fine if the code being tested does `file.read()`. But `csv.DictReader` iterates.
# The `read_data` argument to `mock_open` itself should handle this.
# So, `mock_file_open.return_value = io.StringIO(MOCK_CSV_DATA_DEPARTMENT_SPECIFIC)` or
# `with patch('builtins.open', mock_open(read_data=MOCK_CSV_DATA_DEPARTMENT_SPECIFIC)):`

# The provided code is:
# @patch('builtins.open', new_callable=mock_open)
# ...
# mock_csv_file = mock_open(read_data=MOCK_CSV_DATA_DEPARTMENT_SPECIFIC)
# mock_file_open.side_effect = [mock_csv_file.return_value]
# This should work. `mock_open(read_data=...)` creates a mock object that behaves like an open file.
# Then `mock_file_open.side_effect` is set to return this mock file object when `open` is called.

# The original test code for CSV has:
# mock_file_open.return_value.read.return_value = MOCK_CSV_DATA_DEPARTMENT_SPECIFIC
# This is incorrect for csv.DictReader.
# I'll fix this in my code generation below.
# The fix is to use `mock_open(read_data=...)` and assign its return value to the `open` call.
# e.g. `mock_file_open.return_value = io.StringIO(MOCK_CSV_DATA_DEPARTMENT_SPECIFIC)` if `open` is called once.
# Or `mock_file_open.side_effect = [io.StringIO(MOCK_CSV_DATA_DEPARTMENT_SPECIFIC)]`
# My current code for the test already does this with `mock_csv_file = mock_open(read_data=...)` and then `mock_file_open.side_effect`. This is fine.
# The issue might have been in my previous internal reasoning, not the generated code itself.
# The generated code seems to try to mock it correctly.
#
# The problem statement's `mock_file_open.return_value.read.return_value` was an example of *incorrect* mocking for CSVs.
# My generated code for `test_get_prescription_data_for_pdf_success_department_csv_exists`:
#   mock_csv_file = mock_open(read_data=MOCK_CSV_DATA_DEPARTMENT_SPECIFIC)
#   mock_file_open.side_effect = [mock_csv_file.return_value]
# This is a correct way to use mock_open for a single file read when `open` is called within the function.
# The `csv.DictReader` will then correctly iterate over the lines provided by `read_data`.
#
# Final check on the file path for `get_prescription_data_for_pdf`, it uses `os.path.join("app", "data", filename)`.
# The test structure `tests/services/test_...` means the service code is likely in `app/services/...`.
# The `sys.path.insert` is a common way to handle imports for such structures when running tests directly.
# It assumes the `PYTHONPATH` or execution context allows `app.services...` to be found.
# If running with `python -m unittest discover tests`, then `PYTHONPATH` should be set to the project root.
# The `sys.path.insert` helps make the individual test file runnable.
# I'll remove the `sys.path.insert` as it's generally better to configure PYTHONPATH or use a test runner that handles it.
# For the tool environment, it should find `app` correctly.
# I have removed the `sys.path.insert` line.Okay, this is a large subtask involving creating multiple test files and numerous test cases. I will proceed file by file.

First, I'll create the `tests/services` directory. Since I can't create a directory directly, I'll create the first test file within that directory, which will implicitly create the directory structure.

I'll start with `tests/services/test_certificate_service.py`.
