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
        # print(f"CRITICAL ERROR: reservations.csv not found at {reservations_csv_path}") # Or log this
        return None

    patient_reservation_data = None
    try:
        with open(reservations_csv_path, mode='r', encoding='utf-8-sig') as file:
            reader = csv.DictReader(file)
            for row in reader:
                if row.get('rrn') == patient_rrn:
                    patient_reservation_data = row
                    break
    except FileNotFoundError:
        # print(f"Error: File not found during read: {reservations_csv_path}")
        return None
    except Exception as e:
        # print(f"Error reading {reservations_csv_path}: {e}") # Log other potential CSV errors
        return None

    if not patient_reservation_data:
        # print(f"Info: Patient with rrn {patient_rrn} not found in {reservations_csv_path}.")
        return None

    prescription_names_str = patient_reservation_data.get("prescription_names", "")
    total_fee_str = patient_reservation_data.get("total_fee", "0")

    if prescription_names_str:
        parsed_prescription_names = [name.strip() for name in prescription_names_str.split(',') if name.strip()]
    else:
        parsed_prescription_names = []

    try:
        fetched_total_fee = int(total_fee_str)
    except ValueError:
        # print(f"Warning: Invalid total_fee format '{total_fee_str}' for patient {patient_rrn}. Defaulting to 0.")
        fetched_total_fee = 0

    # Department specific prescription file (e.g., prescriptions_소화기내과.csv)
    department_filename_part = department.lower().replace(" ", "_") # Basic normalization
    filename = f"prescriptions_{department_filename_part}.csv"
    # base_dir is defined above
    filepath = os.path.join(base_dir, "data", filename) # Changed from "app", "data" to "data"

    if not os.path.exists(filepath):
        # Fallback to a generic prescriptions file if department-specific file doesn't exist
        filepath = os.path.join(base_dir, "data", "prescriptions.csv") # Changed from "app", "data"
        if not os.path.exists(filepath):
            # print(f"Error: Prescription details file not found (e.g., {filename} or prescriptions.csv).")
            return None

    all_prescriptions_in_file = []
    try:
        # Use utf-8-sig for prescription files too, in case they have a BOM
        with open(filepath, mode='r', encoding='utf-8-sig') as file:
            reader = csv.DictReader(file)
            for row in reader:
                all_prescriptions_in_file.append(row)
    except FileNotFoundError:
        # print(f"Error: Prescription data file not found at {filepath}")
        return None
    except Exception as e:
        # print(f"Error reading prescription data file {filepath}: {e}")
        return None

    # This check means if prescription names were found in reservation, but no corresponding
    # prescription detail file (e.g. treatment_fees.csv or prescriptions.csv) was loaded,
    # it's an issue. However, to maintain behavior of showing N/A for missing details,
    # we allow it to proceed. If `all_prescriptions_in_file` is empty, `med_detail` will be None.
    # if not all_prescriptions_in_file and parsed_prescription_names:
    #     print(f"Warning: Prescriptions listed for patient {patient_rrn}, but no details found in {filepath}.")
    #     # Proceeding will result in N/A for details.

    selected_prescriptions = []
    if parsed_prescription_names: # Only try to find details if there are names from reservation
        for med_name in parsed_prescription_names:
            # Ensure 'name' in p is stripped for comparison, similar to parsed_prescription_names
            med_detail = next((p for p in all_prescriptions_in_file if p.get('name', '').strip() == med_name), None)
            if med_detail:
                selected_prescriptions.append({
                    "name": med_detail["name"], # Use the name from the details file for consistency
                    "code": med_detail.get("code", "N/A"),
                    "unit_dose": med_detail.get("unit_dose", "1"),
                    "daily_frequency": med_detail.get("daily_frequency", "1"),
                    "total_days": med_detail.get("total_days", "1"),
                })
            else:
                # If a medicine name from reservation is not found in the details file
                selected_prescriptions.append({
                    "name": med_name, "code": "N/A", "unit_dose": "N/A",
                    "daily_frequency": "N/A", "total_days": "N/A",
                })

    # Constructing the prescription data structure
    prescription_data_template = {
        "doctor_name": "김의사", # Placeholder, ideally from reservation or doctor data
        "doctor_license_number": f"{random.randint(1000, 9999)}", # Placeholder
        "department": department, # Passed as argument, originally from reservation
        "prescriptions": selected_prescriptions,
        "total_fee": fetched_total_fee, # Use the fee from reservations.csv
        "issue_date": datetime.now().strftime("%Y-%m-%d")
    }
    return prescription_data_template


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

    pdf_bytes = create_prescription_pdf_bytes(prescription_data)
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
