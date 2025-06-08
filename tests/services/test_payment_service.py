import unittest
from unittest.mock import patch, mock_open
import os
import uuid # For checking payment_id format, though not strictly necessary to mock uuid itself
import sys

# Ensure the app package is importable during test collection
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.services.payment_service import (
    process_new_payment,
    get_payment_details,
    load_department_prescriptions,
    _payments_db # Import for checking db state, use with caution in tests (implementation detail)
)

# Mock data for TREATMENT_FEES_CSV
MOCK_TREATMENT_FEES_CSV_DATA = """Department,Prescription,Fee
내과,감기약 처방,5000
내과,소화제 처방,6000
정형외과,X-레이 촬영,15000
정형외과,물리치료,20000
피부과,피부 연고 처방,7000
"""

class TestPaymentService(unittest.TestCase):

    def setUp(self):
        # Clear the in-memory database before each test
        _payments_db.clear()
        self.patient_id = "test_patient_001"
        self.amount = 10000
        self.method = "card"

    def test_process_new_payment(self):
        initial_db_size = len(_payments_db)
        payment_id = process_new_payment(self.patient_id, self.amount, self.method)

        self.assertIsNotNone(payment_id)
        self.assertTrue(isinstance(payment_id, str))
        # Check if it looks like a UUID (optional, as we don't control uuid.uuid4 format strictly)
        try:
            uuid.UUID(payment_id, version=4)
        except ValueError:
            self.fail("payment_id is not a valid UUID v4 string")

        self.assertEqual(len(_payments_db), initial_db_size + 1)
        new_payment_record = _payments_db[-1]
        self.assertEqual(new_payment_record["payment_id"], payment_id)
        self.assertEqual(new_payment_record["patient_id"], self.patient_id)
        self.assertEqual(new_payment_record["amount"], self.amount)
        self.assertEqual(new_payment_record["method"], self.method)
        self.assertEqual(new_payment_record["status"], "completed")

    def test_get_payment_details_existing(self):
        # Add a payment record first
        payment_id = process_new_payment(self.patient_id, self.amount, self.method)

        retrieved_details = get_payment_details(payment_id)
        self.assertIsNotNone(retrieved_details)
        self.assertEqual(retrieved_details["payment_id"], payment_id)
        self.assertEqual(retrieved_details["patient_id"], self.patient_id)

    def test_get_payment_details_non_existing(self):
        non_existing_id = str(uuid.uuid4())
        retrieved_details = get_payment_details(non_existing_id)
        self.assertIsNone(retrieved_details)

    @patch('app.services.payment_service.os.path.exists', return_value=True)
    @patch('builtins.open')
    def test_load_department_prescriptions_valid_department(self, mock_open_func, mock_path_exists):
        mock_csv_file = mock_open(read_data=MOCK_TREATMENT_FEES_CSV_DATA)
        mock_open_func.return_value = mock_csv_file.return_value

        department = "내과"
        # Patch random.sample to control selection for testing counts and content
        # The service selects min(2, len), min(3, len) items. "내과" has 2 items.
        # So, it will try to select random.randint(min(2,2), min(3,2)) -> random.randint(2,2) -> 2 items
        with patch('app.services.payment_service.random.sample') as mock_random_sample:
            # Simulate random.sample returning the two items for '내과'
            mock_random_sample.return_value = [
                {"name": "감기약 처방", "fee": 5000},
                {"name": "소화제 처방", "fee": 6000}
            ]

            result = load_department_prescriptions(department)

            self.assertNotIn("error", result)
            self.assertIn("prescriptions_for_display", result)
            self.assertIn("prescription_names", result)
            self.assertIn("total_fee", result)

            self.assertEqual(len(result["prescriptions_for_display"]), 2)
            self.assertEqual(result["prescriptions_for_display"][0]["Prescription"], "감기약 처방")
            self.assertEqual(result["prescriptions_for_display"][1]["Fee"], 6000)

            self.assertEqual(len(result["prescription_names"]), 2)
            self.assertIn("감기약 처방", result["prescription_names"])
            self.assertIn("소화제 처방", result["prescription_names"])

            self.assertEqual(result["total_fee"], 11000)
            mock_random_sample.assert_called_once() # Ensure random.sample was called

    @patch('app.services.payment_service.os.path.exists', return_value=True)
    @patch('builtins.open')
    def test_load_department_prescriptions_department_not_found(self, mock_open_func, mock_path_exists):
        mock_csv_file = mock_open(read_data=MOCK_TREATMENT_FEES_CSV_DATA)
        mock_open_func.return_value = mock_csv_file.return_value

        department = "안과" # Not in MOCK_TREATMENT_FEES_CSV_DATA
        result = load_department_prescriptions(department)

        self.assertIn("error", result)
        self.assertTrue(f"No prescriptions found for department: {department}" in result["error"])
        self.assertEqual(result.get("prescriptions", []), []) # or prescriptions_for_display
        self.assertEqual(result.get("total_fee"), 0)

    @patch('app.services.payment_service.os.path.exists', return_value=False)
    def test_load_department_prescriptions_csv_not_found(self, mock_path_exists):
        department = "내과"
        result = load_department_prescriptions(department)

        self.assertIn("error", result)
        self.assertTrue("Data file not found" in result["error"])
        self.assertEqual(result.get("prescriptions", []), [])
        self.assertEqual(result.get("total_fee"), 0)

    @patch('app.services.payment_service.os.path.exists', return_value=True)
    @patch('builtins.open')
    def test_load_department_prescriptions_random_selection_logic(self, mock_open_func, mock_path_exists):
        # Test with a department that has more than 3 items to check random sampling range
        # For this, we need to modify the mock CSV data or use a different department
        # Let's use '정형외과' which has 2 items, so 2 items should be selected.
        mock_csv_file = mock_open(read_data=MOCK_TREATMENT_FEES_CSV_DATA)
        mock_open_func.return_value = mock_csv_file.return_value
        department = "정형외과" # Has 2 items in CSV

        # random.sample will be called to select 2 items from 2 available
        with patch('app.services.payment_service.random.sample') as mock_random_sample:
            # Define what random.sample should return for this specific call
            # These are the actual items for 정형외과
            simulated_sample_return = [
                {"name": "X-레이 촬영", "fee": 15000},
                {"name": "물리치료", "fee": 20000}
            ]
            mock_random_sample.return_value = simulated_sample_return

            result = load_department_prescriptions(department)

            self.assertNotIn("error", result)
            self.assertEqual(len(result["prescriptions_for_display"]), 2)
            self.assertEqual(len(result["prescription_names"]), 2)
            # random.sample(population, k) -> k is num_to_select
            # For 2 items, num_to_select is random.randint(min(2,2), min(3,2)) -> randint(2,2) -> 2
            mock_random_sample.assert_called_once_with(unittest.mock.ANY, 2)

    @patch('app.services.payment_service.os.path.exists', return_value=True)
    @patch('builtins.open')
    @patch('app.services.payment_service.random.sample') # Mock random.sample
    def test_load_department_prescriptions_unexpected_error(self, mock_random_sample, mock_open_func, mock_path_exists):
        mock_csv_file = mock_open(read_data=MOCK_TREATMENT_FEES_CSV_DATA)
        mock_open_func.return_value = mock_csv_file.return_value

        # Configure random.sample to raise an unexpected error
        mock_random_sample.side_effect = RuntimeError("Simulated unexpected error from random.sample")

        department = "내과" # A department that would normally succeed
        result = load_department_prescriptions(department)

        self.assertIn("error", result, "Result should contain an 'error' key on unexpected exception.")
        self.assertTrue(
            result["error"].startswith("An unexpected server error occurred"),
            f"Error message '{result['error']}' does not start with the expected prefix."
        )
        self.assertIn(
            "Simulated unexpected error from random.sample",
            result["error"],
            "The original error message should be part of the reported error."
        )
        # Check that the default error structure is returned
        self.assertEqual(result.get("prescriptions", []), [], "Prescriptions should be empty on error.")
        self.assertEqual(result.get("total_fee"), 0, "Total_fee should be 0 on error.")
        # Also ensure other keys that might exist on success are not there or are empty
        self.assertEqual(result.get("prescriptions_for_display", []), [], "Prescriptions_for_display should be empty or not present on error.")
        self.assertEqual(result.get("prescription_names", []), [], "Prescription_names should be empty or not present on error.")


if __name__ == '__main__':
    unittest.main()
