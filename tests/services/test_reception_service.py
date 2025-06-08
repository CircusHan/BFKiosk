import unittest
from unittest.mock import patch, mock_open, MagicMock
import os
from datetime import datetime
import sys

# Ensure the app package is importable during test collection
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.services.reception_service import (
    lookup_reservation,
    handle_scan_action,
    handle_manual_action,
    handle_choose_symptom_action,
    new_ticket, # Import if testing directly, or it's tested via handle_choose_symptom_action
    fake_scan_rrn, # Import if testing directly
    SYMPTOMS, # Import for context if needed
    SYM_TO_DEPT # Import for context if needed
)

MOCK_RESERVATIONS_CSV_DATA = """name,rrn,department,time,location,doctor,status,transcription,amount
김예약,850101-1234567,내과,10:00,본관1층,닥터김,Pending,,0
박테스트,920202-2345678,외과,14:30,별관2층,닥터박,Pending,,0
"""

class TestReceptionService(unittest.TestCase):

    @patch('app.services.reception_service.os.path.exists', return_value=True)
    @patch('builtins.open')
    def test_lookup_reservation_existing(self, mock_open_func, mock_path_exists):
        mock_csv_file = mock_open(read_data=MOCK_RESERVATIONS_CSV_DATA)
        mock_open_func.return_value = mock_csv_file.return_value

        name = "김예약"
        rrn = "850101-1234567"
        result = lookup_reservation(name, rrn)

        self.assertIsNotNone(result)
        self.assertEqual(result["name"], name)
        self.assertEqual(result["rrn"], rrn)
        self.assertEqual(result["department"], "내과")
        self.assertEqual(result["status"], "Pending")
        self.assertEqual(result["transcription"], "")
        self.assertEqual(result["amount"], "0") # Values from DictReader are strings

    @patch('app.services.reception_service.os.path.exists', return_value=True)
    @patch('builtins.open')
    def test_lookup_reservation_non_existing(self, mock_open_func, mock_path_exists):
        mock_csv_file = mock_open(read_data=MOCK_RESERVATIONS_CSV_DATA)
        mock_open_func.return_value = mock_csv_file.return_value

        name = "최미예약"
        rrn = "991212-2000000"
        result = lookup_reservation(name, rrn)
        self.assertIsNone(result)

    @patch('app.services.reception_service.os.path.exists', return_value=False)
    def test_lookup_reservation_csv_not_found(self, mock_path_exists):
        name = "김예약"
        rrn = "850101-1234567"
        result = lookup_reservation(name, rrn)
        self.assertIsNone(result)
        # Check console for "Warning: RESV_CSV not found..." (optional, depends on logging setup)

    @patch('app.services.reception_service.fake_scan_rrn')
    @patch('app.services.reception_service.lookup_reservation')
    def test_handle_scan_action_reservation_exists(self, mock_lookup_reservation, mock_fake_scan_rrn):
        scanned_name = "박테스트"
        scanned_rrn = "920202-2345678"
        reservation_data = {"Name": scanned_name, "RRN": scanned_rrn, "Department": "외과"}

        mock_fake_scan_rrn.return_value = (scanned_name, scanned_rrn)
        mock_lookup_reservation.return_value = reservation_data

        result = handle_scan_action()

        self.assertEqual(result["name"], scanned_name)
        self.assertEqual(result["rrn"], scanned_rrn)
        self.assertEqual(result["reservation_details"], reservation_data)
        mock_fake_scan_rrn.assert_called_once()
        mock_lookup_reservation.assert_called_once_with(scanned_name, scanned_rrn)

    @patch('app.services.reception_service.fake_scan_rrn')
    @patch('app.services.reception_service.lookup_reservation')
    def test_handle_scan_action_no_reservation(self, mock_lookup_reservation, mock_fake_scan_rrn):
        scanned_name = "없는사람"
        scanned_rrn = "000000-0000000"

        mock_fake_scan_rrn.return_value = (scanned_name, scanned_rrn)
        mock_lookup_reservation.return_value = None # No reservation found

        result = handle_scan_action()

        self.assertEqual(result["name"], scanned_name)
        self.assertEqual(result["rrn"], scanned_rrn)
        self.assertIsNone(result["reservation_details"])

    @patch('app.services.reception_service.lookup_reservation')
    def test_handle_manual_action_reservation_exists(self, mock_lookup_reservation):
        manual_name = "김예약"
        manual_rrn = "850101-1234567"
        reservation_data = {"Name": manual_name, "RRN": manual_rrn, "Department": "내과"}
        mock_lookup_reservation.return_value = reservation_data

        result = handle_manual_action(manual_name, manual_rrn)

        self.assertEqual(result, reservation_data)
        mock_lookup_reservation.assert_called_once_with(manual_name, manual_rrn)

    @patch('app.services.reception_service.lookup_reservation')
    def test_handle_manual_action_no_reservation(self, mock_lookup_reservation):
        manual_name = "없는사람"
        manual_rrn = "000000-0000000"
        mock_lookup_reservation.return_value = None

        result = handle_manual_action(manual_name, manual_rrn)
        self.assertIsNone(result)

    def test_handle_manual_action_empty_input(self):
        # Service function itself has a basic check for empty name/rrn
        result_empty_name = handle_manual_action("", "123")
        result_empty_rrn = handle_manual_action("test", "")
        self.assertIsNone(result_empty_name)
        self.assertIsNone(result_empty_rrn)


    @patch('app.services.reception_service.new_ticket')
    def test_handle_choose_symptom_action_known_symptom(self, mock_new_ticket):
        symptom_key = "headache" # Key for "두통" which maps to "신경과"
        expected_department = SYM_TO_DEPT[symptom_key]
        fake_ticket = "신경과TICKET123"
        mock_new_ticket.return_value = fake_ticket

        result = handle_choose_symptom_action(symptom_key)

        self.assertEqual(result["department"], expected_department)
        self.assertEqual(result["ticket"], fake_ticket)
        mock_new_ticket.assert_called_once_with(expected_department)

    @patch('app.services.reception_service.new_ticket')
    def test_handle_choose_symptom_action_unknown_symptom(self, mock_new_ticket):
        symptom_key = "unknown_symptom_key"
        # Should default to "etc" which maps to "가정의학과"
        expected_department = SYM_TO_DEPT["etc"]
        fake_ticket = "가정의학과TICKET456"
        mock_new_ticket.return_value = fake_ticket

        result = handle_choose_symptom_action(symptom_key)

        self.assertEqual(result["department"], expected_department)
        self.assertEqual(result["ticket"], fake_ticket)
        mock_new_ticket.assert_called_once_with(expected_department)

    def test_new_ticket_format(self):
        # Test the actual new_ticket function's format
        department = "정형외과"
        # Mock datetime and random.randint for predictable ticket numbers
        with patch('app.services.reception_service.datetime') as mock_datetime, \
             patch('app.services.reception_service.random.randint') as mock_randint:

            mock_now = MagicMock()
            mock_now.strftime.return_value = "100000" # HHMMSS
            mock_datetime.now.return_value = mock_now
            mock_randint.return_value = 50 # Random int part

            ticket = new_ticket(department)

            # Expected format: First letter of department + HHMMSS + random_int
            # 정형외과 -> 정
            # For simplicity, using first char '정'. Actual service uses department[0]
            # If SYM_TO_DEPT values are Korean, department[0] will be Korean.
            # The service has: dept_code = department[0] if department else "X"
            # So for "정형외과", dept_code will be "정"
            expected_ticket_prefix = department[0]
            self.assertTrue(ticket.startswith(expected_ticket_prefix))
            self.assertIn("10000050", ticket) # HHMMSS + randint
            mock_datetime.now.assert_called_once()
            mock_randint.assert_called_once_with(10,99)

    @patch('app.services.reception_service.os.path.exists', return_value=True)
    @patch('builtins.open')
    def test_fake_scan_rrn_reads_from_csv(self, mock_open_func, mock_path_exists):
        mock_csv_file = mock_open(read_data=MOCK_RESERVATIONS_CSV_DATA)
        mock_open_func.return_value = mock_csv_file.return_value

        with patch('app.services.reception_service.random.choice') as mock_random_choice:
            # Simulate random.choice returning the first entry from our mock CSV data
            # The data read by csv.DictReader will be a list of dicts
            # Example: [{'Name': '김예약', 'RRN': '850101-1234567', ...}, ...]
            mock_random_choice.return_value = {
                "name": "김예약", "rrn": "850101-1234567", "department": "내과",
                "time": "10:00", "location": "본관1층", "doctor": "닥터김",
                "status": "Pending", "transcription": "", "amount": "0"
            }

            name, rrn = fake_scan_rrn()

            self.assertEqual(name, "김예약")
            self.assertEqual(rrn, "850101-1234567")
            mock_random_choice.assert_called_once()

    @patch('app.services.reception_service.os.path.exists', return_value=False)
    def test_fake_scan_rrn_csv_not_found_fallback(self, mock_path_exists):
        # Test fallback behavior when CSV is not found
        name, rrn = fake_scan_rrn()
        # Default fallback from the function
        self.assertEqual(name, "이서연")
        self.assertEqual(rrn, "920202-2345678")


if __name__ == '__main__':
    unittest.main()
