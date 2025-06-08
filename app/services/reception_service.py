import csv
import os
import random
import sys # Added for logging
from datetime import datetime

# Path constants
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
RESV_CSV = os.path.join(BASE_DIR, "data", "reservations.csv")

# Symptoms and department mapping (structure matching original route for template compatibility)
SYMPTOMS = [
    ("fever",   "발열‧오한"), ("cough",  "기침‧가래"), ("soreth",  "인후통"),
    ("stomach", "복통‧소화불량"), ("diarr", "설사"),  ("headache", "두통"),
    ("dizzy",   "어지럼증"),    ("skin",  "피부발진"), ("injury",  "타박상‧상처"),
    ("etc",     "기타")
]

# SYM_TO_DEPT uses the 'value' part of the SYMPTOMS tuples as keys
SYM_TO_DEPT = {
    "fever": "내과",
    "cough": "호흡기내과",
    "soreth": "이비인후과",
    "stomach": "소화기내과",
    "diarr": "감염내과",   # Assuming 감염내과 for 설사 based on common practice
    "headache": "신경과",
    "dizzy": "신경과",      # Or 이비인후과, context dependent. Sticking to original.
    "skin": "피부과",
    "injury": "외과",
    "etc": "가정의학과"     # General fallback
}
# Note: The original SYM_TO_DEPT in routes.py had different Korean symptoms than my initial service version.
# I've updated SYM_TO_DEPT keys to match the first element of the SYMPTOMS tuples (e.g., "fever", "cough")
# which is likely how the form would submit the symptom value.

# Helper functions (moved from routes)

def fake_scan_rrn() -> tuple[str, str]:
    """
    주민등록번호 스캔 흉내 (실제 스캐너 대신 임의의 데이터를 생성)
    """
    _func_args = locals()
    _module_path = sys.modules[__name__].__name__ if __name__ in sys.modules else __file__
    print(f"ENTERING: {_module_path}.fake_scan_rrn(args={{_func_args}})")
    # CSV 파일에서 임의의 환자 정보 읽기 (데모용)
    try:
        with open(RESV_CSV, mode="r", encoding="utf-8-sig") as f:
            reservations = list(csv.DictReader(f))
        if not reservations:
            # Fallback if CSV is empty or not found
            return "김민준", "900101-1234567"

        random_patient = random.choice(reservations)
        return random_patient["name"], random_patient["rrn"]
    except FileNotFoundError:
        # Fallback if CSV is not found
        print(f"Warning: {RESV_CSV} not found. Using default fake scan data.")
        return "이서연", "920202-2345678"
    except Exception as e:
        print(f"Error in fake_scan_rrn reading {RESV_CSV}: {e}")
        return "박도윤", "950505-1010101"


def lookup_reservation(name: str, rrn: str) -> dict | None:
    """
    예약 내역 조회 (이름과 주민번호로 조회)
    """
    _func_args = locals()
    _module_path = sys.modules[__name__].__name__ if __name__ in sys.modules else __file__
    print(f"ENTERING: {_module_path}.lookup_reservation(args={{_func_args}})")
    try:
        with open(RESV_CSV, mode="r", encoding="utf-8-sig") as f:
            reservations = list(csv.DictReader(f))

        for res in reservations:
            if res["name"] == name and res["rrn"] == rrn:
                return res # Return the entire reservation dict
        return None
    except FileNotFoundError:
        print(f"Warning: {RESV_CSV} not found in lookup_reservation.")
        return None
    except Exception as e:
        print(f"Error in lookup_reservation reading {RESV_CSV}: {e}")
        return None

def new_ticket(department: str) -> str:
    """
    새로운 대기표 발급 (간단한 규칙으로 생성)
    """
    _func_args = locals()
    _module_path = sys.modules[__name__].__name__ if __name__ in sys.modules else __file__
    print(f"ENTERING: {_module_path}.new_ticket(args={{_func_args}})")
    now = datetime.now()
    dept_code = department[0] if department else "X" # Use first letter of department
    ticket_num = f"{dept_code}{now.strftime('%H%M%S')}{random.randint(10,99)}"
    return ticket_num


def update_reservation_status(patient_rrn: str, new_status: str, **kwargs) -> bool:
    """
    Updates the status of a patient's reservation in reservations.csv.
    Can also update other reservation fields (e.g., 'department', 'ticket_number', 'name')
    by passing them as keyword arguments. All values will be stored as strings.
    """
    _func_args = locals()
    _module_path = sys.modules[__name__].__name__ if __name__ in sys.modules else __file__
    print(f"ENTERING: {_module_path}.update_reservation_status(args={{_func_args}})")

    if not os.path.exists(RESV_CSV):
        # print(f"Error: {RESV_CSV} not found.") # Optional: for server-side logging
        return False

    rows = []
    original_fieldnames = None
    updated = False

    try:
        with open(RESV_CSV, mode='r', newline='', encoding='utf-8-sig') as csvfile:
            reader = csv.DictReader(csvfile)
            original_fieldnames = reader.fieldnames
            # Ensure 'rrn' and 'status' are valid fieldnames
            if not original_fieldnames or not all(field in original_fieldnames for field in ['rrn', 'status']):
                # print("Error: CSV headers are missing 'rrn' or 'status'.") # Optional
                return False
            rows = list(reader)

        for i, row in enumerate(rows):
            if row.get('rrn') == patient_rrn:
                rows[i]['status'] = str(new_status) # Ensure status is also a string

                # Update other fields from kwargs if they are valid column names
                for key, value in kwargs.items():
                    if key in original_fieldnames: # Ensure the key is a valid column
                        rows[i][key] = str(value) # Store all CSV data as strings
                    else:
                        # Optional: Log a warning if a kwarg key is not a valid fieldname
                        print(f"Warning: In update_reservation_status, '{key}' is not a valid field in reservations.csv. Cannot update.")

                updated = True
                # RRN should be unique, so we can break after finding and updating.
                break

        if updated:
            with open(RESV_CSV, mode='w', newline='', encoding='utf-8') as csvfile:
                if not original_fieldnames: # Should have been caught earlier
                    return False
                writer = csv.DictWriter(csvfile, fieldnames=original_fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            return True
        else:
            # print(f"Info: Patient RRN {patient_rrn} not found for status update.") # Optional
            return False # Patient not found

    except FileNotFoundError: # Should be caught by os.path.exists, but as a safeguard
        # print(f"Error: File {RESV_CSV} disappeared during update operation.") # Optional
        return False
    except Exception as e:
        # print(f"Error updating reservation status for RRN {patient_rrn}: {e}") # Optional
        return False


# Service action functions

def handle_scan_action() -> dict:
    """
    Handles the 'scan' action: simulates RRN scan and looks up reservation.
    Returns a dictionary with name, rrn, and reservation_details.
    """
    _func_args = locals()
    _module_path = sys.modules[__name__].__name__ if __name__ in sys.modules else __file__
    print(f"ENTERING: {_module_path}.handle_scan_action(args={{_func_args}})")
    name, rrn = fake_scan_rrn()
    reservation_details = lookup_reservation(name, rrn)
    return {
        "name": name,
        "rrn": rrn,
        "reservation_details": reservation_details
    }

def handle_manual_action(name: str, rrn: str) -> dict | None:
    """
    Handles the 'manual' input action: looks up reservation.
    Returns reservation_details dictionary or None.
    """
    _func_args = locals()
    _module_path = sys.modules[__name__].__name__ if __name__ in sys.modules else __file__
    print(f"ENTERING: {_module_path}.handle_manual_action(args={{_func_args}})")
    # Basic validation, though more robust validation might be in the route or a shared util
    if not name or not rrn: # Or more specific RRN format validation
        return None # Or raise ValueError

    reservation_details = lookup_reservation(name, rrn)
    return reservation_details # This will be None if not found, or the dict if found

def handle_choose_symptom_action(symptom: str) -> dict:
    """
    Handles the 'choose_symptom' action: determines department and issues a new ticket.
    Returns a dictionary with department and ticket number.
    """
    _func_args = locals()
    _module_path = sys.modules[__name__].__name__ if __name__ in sys.modules else __file__
    print(f"ENTERING: {_module_path}.handle_choose_symptom_action(args={{_func_args}})")
    department = SYM_TO_DEPT.get(symptom, SYM_TO_DEPT.get("etc", "가정의학과")) # Default to "가정의학과" if symptom not in map
    ticket = new_ticket(department)
    return {
        "department": department,
        "ticket": ticket
    }

DEFAULT_FIELDNAMES = [
    "name", "rrn", "time", "department", "ticket_number",
    "location", "doctor", "status", "prescription_names", "total_fee"
]

def add_new_patient_reception(name: str, rrn: str, department: str, ticket_number: str, initial_status: str = "Registered") -> bool:
    """
    Appends a new patient reception record to reservations.csv.
    If the CSV doesn't exist, it creates it with headers.
    """
    _func_args = locals()
    _module_path = sys.modules[__name__].__name__ if __name__ in sys.modules else __file__
    print(f"ENTERING: {_module_path}.add_new_patient_reception(args={{_func_args}})")

    file_exists = os.path.exists(RESV_CSV)
    if not file_exists:
        print(f"Info: {RESV_CSV} not found, will be created with headers.")

    try:
        with open(RESV_CSV, mode='a', newline='', encoding='utf-8') as csvfile:
            # Use DEFAULT_FIELDNAMES consistently
            writer = csv.DictWriter(csvfile, fieldnames=DEFAULT_FIELDNAMES)

            if not file_exists or os.path.getsize(RESV_CSV) == 0:
                writer.writeheader()

            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            new_row = {
                "name": name,
                "rrn": rrn,
                "time": current_time,
                "department": department,
                "ticket_number": ticket_number,
                "location": "",  # Default empty
                "doctor": "",    # Default empty
                "status": initial_status,
                "prescription_names": "", # Default empty
                "total_fee": "0"          # Default 0
            }
            writer.writerow(new_row)
        return True
    except Exception as e:
        print(f"Error adding new patient reception for RRN {rrn}: {e}")
        return False
