import csv
import os
import random
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
    # CSV 파일에서 임의의 환자 정보 읽기 (데모용)
    try:
        with open(RESV_CSV, mode="r", encoding="utf-8-sig") as f:
            reservations = list(csv.DictReader(f))
        if not reservations:
            # Fallback if CSV is empty or not found
            return "김민준", "900101-1234567"

        random_patient = random.choice(reservations)
        return random_patient["Name"], random_patient["RRN"]
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
    try:
        with open(RESV_CSV, mode="r", encoding="utf-8-sig") as f:
            reservations = list(csv.DictReader(f))

        for res in reservations:
            if res["Name"] == name and res["RRN"] == rrn:
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
    now = datetime.now()
    dept_code = department[0] if department else "X" # Use first letter of department
    ticket_num = f"{dept_code}{now.strftime('%H%M%S')}{random.randint(10,99)}"
    return ticket_num


# Service action functions

def handle_scan_action() -> dict:
    """
    Handles the 'scan' action: simulates RRN scan and looks up reservation.
    Returns a dictionary with name, rrn, and reservation_details.
    """
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
    department = SYM_TO_DEPT.get(symptom, SYM_TO_DEPT["기타"]) # Default to "가정의학과" if symptom not in map
    ticket = new_ticket(department)
    return {
        "department": department,
        "ticket": ticket
    }
