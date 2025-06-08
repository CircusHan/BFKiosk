import csv
import csv
import os
import random
from datetime import datetime, timedelta # Moved timedelta here
from io import BytesIO

from app.utils.pdf_generator import create_prescription_pdf_bytes, create_confirmation_pdf_bytes, MissingKoreanFontError


def get_prescription_data_for_pdf(department: str, last_prescriptions: list, last_total_fee: int):
    """
    Loads and prepares prescription data for PDF generation.
    This function encapsulates logic from the original _load_prescription_data
    and any other data preparation needed for the prescription PDF.
    """
    if not last_prescriptions:
        return None

    # Simulate loading prescription details from a CSV file based on department
    # This part is adapted from the original _load_prescription_data
    filename = f"prescriptions_{department.lower()}.csv"
    filepath = os.path.join("app", "data", filename)

    if not os.path.exists(filepath):
        # Fallback to a generic prescriptions file if department-specific file doesn't exist
        filepath = os.path.join("app", "data", "prescriptions.csv")
        if not os.path.exists(filepath):
            return None # Or raise an error

    all_prescriptions_in_file = []
    try:
        with open(filepath, mode='r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                all_prescriptions_in_file.append(row)
    except FileNotFoundError:
        return None # Or raise an error

    if not all_prescriptions_in_file:
        return None

    # The original logic selected a random number of prescriptions.
    # We'll use the `last_prescriptions` passed from the session.
    selected_prescriptions = []
    for med_name in last_prescriptions:
        # Find the details for each prescribed medicine
        med_detail = next((p for p in all_prescriptions_in_file if p['name'] == med_name), None)
        if med_detail:
            selected_prescriptions.append({
                "name": med_detail["name"],
                "code": med_detail["code"],
                "unit_dose": med_detail.get("unit_dose", "1"), # Assuming default if not present
                "daily_frequency": med_detail.get("daily_frequency", "1"), # Assuming default
                "total_days": med_detail.get("total_days", "1"), # Assuming default
            })
        else:
            # Handle case where a medicine from last_prescriptions is not found in the CSV
            # This might indicate a data consistency issue or a need for a more robust lookup
            selected_prescriptions.append({
                "name": med_name,
                "code": "N/A", # Or some other placeholder
                "unit_dose": "N/A",
                "daily_frequency": "N/A",
                "total_days": "N/A",
            })


    # Constructing the prescription data structure, patient details will be added later
    prescription_data_template = {
        "doctor_name": "김의사", # Placeholder
        "doctor_license_number": f"{random.randint(1000, 9999)}", # Placeholder
        "department": department,
        "prescriptions": selected_prescriptions,
        "total_fee": last_total_fee, # Use the fee from the session
        "issue_date": datetime.now().strftime("%Y-%m-%d")
    }
    return prescription_data_template


def prepare_prescription_pdf(patient_name: str, patient_rrn: str, department: str, prescription_details: dict):
    """
    Prepares the prescription PDF using the provided data.
    """
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
