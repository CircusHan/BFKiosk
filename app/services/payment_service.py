import uuid
import random
import csv
import os

# In-memory "database" for payments
_payments_db = []

# Define BASE_DIR and TREATMENT_FEES_CSV path
# Assuming the structure is app/services/payment_service.py
# and data/treatment_fees.csv is relative to the project root.
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
TREATMENT_FEES_CSV = os.path.join(BASE_DIR, "data", "treatment_fees.csv")


def process_new_payment(patient_id: str, amount: int, method: str) -> str:
    """
    Processes a new payment, stores it, and returns a unique payment ID.
    """
    payment_id = str(uuid.uuid4())
    payment_record = {
        "payment_id": payment_id,
        "patient_id": patient_id,
        "amount": amount,
        "method": method,
        "status": "completed",  # Assuming payment is always successful for now
        "timestamp": uuid.uuid4().hex # Using hex for a simple timestamp-like string
    }
    _payments_db.append(payment_record)
    return payment_id


def get_payment_details(payment_id: str) -> dict | None:
    """
    Retrieves payment details for a given payment ID.
    Returns the payment record or None if not found.
    """
    for payment in _payments_db:
        if payment["payment_id"] == payment_id:
            return payment
    return None


def load_department_prescriptions(department: str) -> dict:
    """
    Loads prescription data for a given department from TREATMENT_FEES_CSV.
    Selects 2-3 random prescriptions and calculates the total fee.
    Returns a dict with 'prescriptions' and 'total_fee'.
    Returns {'error': message} if an issue occurs.
    """
    if not os.path.exists(TREATMENT_FEES_CSV):
        return {"error": f"Data file not found: {TREATMENT_FEES_CSV}", "prescriptions": [], "total_fee": 0}

    department_prescriptions_details = []
    try:
        with open(TREATMENT_FEES_CSV, newline="", encoding="utf-8-sig") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                if row["Department"].strip().lower() == department.lower(): # Case-insensitive department matching
                    try:
                        department_prescriptions_details.append(
                            {"name": row["Prescription"], "fee": int(row["Fee"])}
                        )
                    except ValueError:
                         return {"error": f"Invalid fee format for {row['Prescription']} in {department}.", "prescriptions": [], "total_fee": 0}
    except Exception as e:
        return {"error": f"Error reading or parsing CSV: {str(e)}", "prescriptions": [], "total_fee": 0}

    if not department_prescriptions_details:
        # If no prescriptions for the department, it's not necessarily an "error" for the caller,
        # but could be seen as "no items found".
        return {"error": f"No prescriptions found for department: {department}", "prescriptions": [], "total_fee": 0}

    num_to_select = random.randint(min(2, len(department_prescriptions_details)), min(3, len(department_prescriptions_details)))
    if len(department_prescriptions_details) == 1: # if only one, select that one
        num_to_select = 1

    selected_prescriptions_objects = random.sample(department_prescriptions_details, num_to_select)

    # selected_prescription_names = [item['name'] for item in selected_prescriptions_objects]
    total_fee = sum(item["fee"] for item in selected_prescriptions_objects)

    # Format for client-side display (expects "Prescription" and "Fee" keys)
    prescriptions_for_display = [
        {"Prescription": item["name"], "Fee": item["fee"]} for item in selected_prescriptions_objects
    ]
    # Format for session (list of names)
    prescription_names = [item['name'] for item in selected_prescriptions_objects]

    return {
        "prescriptions_for_display": prescriptions_for_display, # For AJAX response to client
        "prescription_names": prescription_names,             # For session storage
        "total_fee": total_fee
    }
