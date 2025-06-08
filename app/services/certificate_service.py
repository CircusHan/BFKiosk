import csv
import os
import random
import sys # Added for logging
from datetime import datetime, timedelta # Moved timedelta here
from io import BytesIO

from app.utils.pdf_generator import create_prescription_pdf_bytes, create_confirmation_pdf_bytes, MissingKoreanFontError


def get_prescription_data_for_pdf(patient_rrn: str, department: str):
    """
    Loads and prepares prescription data for PDF generation by fetching
    details from reservations.csv and then prescription item details.
    """
    _func_args = locals()
    _module_path = sys.modules[__name__].__name__ if __name__ in sys.modules else __file__
    print(f"ENTERING: {_module_path}.get_prescription_data_for_pdf(args={{_func_args}})")
    try:
        # Determine project base directory
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
        reservations_csv_path = os.path.join(base_dir, "data", "reservations.csv")
    except NameError:
        # Fallback if __file__ is not defined
        reservations_csv_path = os.path.join("data", "reservations.csv") # Assumes PWD is project root

    if not os.path.exists(reservations_csv_path):
        return ("FILE_NOT_FOUND", "예약 데이터 파일을 찾을 수 없습니다.")

    patient_reservation_data = None
    try:
        with open(reservations_csv_path, mode='r', encoding='utf-8-sig') as file:
            reader = csv.DictReader(file)
            for row in reader:
                if row.get('rrn') == patient_rrn:
                    patient_reservation_data = row
                    break
    except FileNotFoundError: # Should be caught by os.path.exists, but good for robustness
        return ("FILE_NOT_FOUND", "예약 데이터 파일을 찾을 수 없습니다.")
    except Exception as e:
        # print(f"Error reading {reservations_csv_path}: {e}") # For server-side debugging
        return ("DATA_ERROR", "예약 데이터 처리 중 오류가 발생했습니다.")

    if not patient_reservation_data:
        return ("NOT_FOUND", "해당 환자의 예약 정보를 찾을 수 없습니다.")

    # Extract data and perform refined status/fee checks
    actual_status = patient_reservation_data.get("status")
    total_fee_str = patient_reservation_data.get("total_fee", "0") # Keep this for fee calculation

    try:
        fetched_total_fee = int(total_fee_str)
    except ValueError:
        # print(f"Warning: Invalid total_fee format '{total_fee_str}' for patient {patient_rrn}. Defaulting to 0.") # Server-side log
        fetched_total_fee = 0 # Default to 0 if conversion fails

    if actual_status == 'Pending':
        return ("NEEDS_RECEPTION_COMPLETION", f"접수를 먼저 완료해주세요. 현재 상태: {actual_status}")
    elif actual_status != 'Paid': # Covers 'Registered' and any other non-'Paid', non-'Pending' status
        return ("NEEDS_PAYMENT", f"수납을 먼저 완료해주세요. 현재 상태: {actual_status if actual_status else '알 수 없음'}")
    else:  # Status is 'Paid'
        if fetched_total_fee <= 0:
            return ("ZERO_FEE_PAID", "결제된 금액이 0원 이하입니다. 유효한 처방전 발급이 불가능합니다. 관리자에게 문의하세요.")
        else:
            # This is the "OK" case, proceed to prepare and return prescription data
            doctor_name_from_reservation = patient_reservation_data.get("doctor", "김의사") # Default if not found

            reservation_time_str = patient_reservation_data.get("time")
            issue_date_for_pdf = datetime.now().strftime("%Y-%m-%d") # Default to current date
            if reservation_time_str:
                try:
                    # Assuming reservation_time_str is like "YYYY-MM-DD HH:MM"
                    reservation_datetime_obj = datetime.strptime(reservation_time_str.split(" ")[0], "%Y-%m-%d")
                    issue_date_for_pdf = reservation_datetime_obj.strftime("%Y-%m-%d")
                except ValueError:
                    # If parsing fails, keep default (current date)
                    pass # Optionally log this: print(f"Warning: Could not parse date from '{reservation_time_str}'")

            prescription_names_str = patient_reservation_data.get("prescription_names", "")
            if prescription_names_str:
                parsed_prescription_names = [name.strip() for name in prescription_names_str.split(',') if name.strip()]
            else:
                parsed_prescription_names = []

            treatment_fees_path = os.path.join(base_dir, "data", "treatment_fees.csv")
            treatment_fee_map = {}
            if os.path.exists(treatment_fees_path):
                try:
                    with open(treatment_fees_path, newline="", encoding="utf-8-sig") as fee_file:
                        fee_reader = csv.DictReader(fee_file)
                        for row in fee_reader:
                            treatment_fee_map[row.get("Prescription", "").strip()] = int(row.get("Fee", 0))
                except Exception:
                    # If CSV reading fails, fall back to zero fees
                    treatment_fee_map = {}

            selected_prescriptions = []
            for med_name in parsed_prescription_names:
                fee_val = treatment_fee_map.get(med_name, 0)
                selected_prescriptions.append({"name": med_name, "fee": fee_val})

            # department argument is used here
            prescription_data_template = {
                "doctor_name": doctor_name_from_reservation,
                "doctor_license_number": f"{random.randint(1000, 9999)}", # Existing placeholder
                "department": department,
                "prescriptions": selected_prescriptions,
                "total_fee": fetched_total_fee,
                "issue_date": issue_date_for_pdf # Use formatted issue date
            }
            return ("OK", prescription_data_template)


def prepare_prescription_pdf(patient_name: str, patient_rrn: str, department: str, prescription_details: dict):
    """
    Prepares the prescription PDF using the provided data.
    """
    _func_args = locals()
    _module_path = sys.modules[__name__].__name__ if __name__ in sys.modules else __file__
    print(f"ENTERING: {_module_path}.prepare_prescription_pdf(args={{_func_args}})")
    if not prescription_details:
        return None, None

    # Add patient information to the prescription data
    prescription_data = prescription_details.copy() # Avoid modifying the input dict directly
    prescription_data["patient_name"] = patient_name
    prescription_data["patient_rrn"] = patient_rrn

    # Call with explicit arguments matching the updated signature
    pdf_bytes = create_prescription_pdf_bytes(
        patient_name=prescription_data["patient_name"],
        patient_rrn=prescription_data["patient_rrn"],
        department=prescription_data["department"],
        prescriptions=prescription_data["prescriptions"],
        total_fee=prescription_data["total_fee"],
        doctor_name=prescription_data["doctor_name"],
        issue_date=prescription_data["issue_date"]
    )
    filename = f"prescription_{patient_name}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
    return pdf_bytes, filename


def prepare_medical_confirmation_pdf(patient_name: str, patient_rrn: str, disease_name: str):
    """
    Prepares the medical confirmation PDF.
    """
    _func_args = locals()
    _module_path = sys.modules[__name__].__name__ if __name__ in sys.modules else __file__
    print(f"ENTERING: {_module_path}.prepare_medical_confirmation_pdf(args={{_func_args}})")
    # For confirmation, we might need a diagnosis date.
    # This could come from session or be fixed for simplicity here.
    date_of_diagnosis = (datetime.now() - timedelta(days=random.randint(1, 30))).strftime("%Y-%m-%d") # Simulate a past diagnosis
    date_of_issue = datetime.now().strftime("%Y-%m-%d")

    pdf_bytes = create_confirmation_pdf_bytes(
        patient_name=patient_name,
        patient_rrn=patient_rrn,
        disease_name=disease_name, # department is used as disease_name
        date_of_diagnosis=date_of_diagnosis,
        date_of_issue=date_of_issue
    )
    filename = f"medical_confirmation_{patient_name}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
    return pdf_bytes, filename
