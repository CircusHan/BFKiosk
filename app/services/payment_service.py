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
    if not os.path.exists(TREATMENT_FEES_CSV):
        return {"error": f"Data file not found: {TREATMENT_FEES_CSV}", "prescriptions": [], "total_fee": 0}

    try: # New top-level try block
        department_prescriptions_details = []
        try: # Inner try for CSV processing (can be kept or simplified)
            with open(TREATMENT_FEES_CSV, newline="", encoding="utf-8-sig") as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    if row["Department"].strip().lower() == department.lower():
                        try:
                            department_prescriptions_details.append(
                                {"name": row["Prescription"], "fee": int(row["Fee"])}
                            )
                        except ValueError:
                             return {"error": f"Invalid fee format for {row['Prescription']} in {department}.", "prescriptions": [], "total_fee": 0}
        except Exception as csv_e: # Catch errors during CSV read/parse specifically
            # It's good practice to log csv_e here for debugging
            return {"error": f"Error reading or parsing CSV: {str(csv_e)}", "prescriptions": [], "total_fee": 0}

        if not department_prescriptions_details:
            # This check is important for departments with no specific prescriptions.
            return {"error": f"No prescriptions found for department: {department}", "prescriptions": [], "total_fee": 0}

        # Determine number of prescriptions to select
        # Ensure num_to_select is valid even if department_prescriptions_details is short
        if len(department_prescriptions_details) == 0: # Should ideally be caught by 'if not ...'
             num_to_select = 0
        elif len(department_prescriptions_details) == 1:
            num_to_select = 1
        else: # len is 2 or more
            num_to_select = random.randint(min(2, len(department_prescriptions_details)), min(3, len(department_prescriptions_details)))

        selected_prescriptions_objects = [] # Initialize to handle num_to_select = 0
        if num_to_select > 0 :
             selected_prescriptions_objects = random.sample(department_prescriptions_details, num_to_select)

        total_fee = sum(item["fee"] for item in selected_prescriptions_objects)
        prescriptions_for_display = [
            {"Prescription": item["name"], "Fee": item["fee"]} for item in selected_prescriptions_objects
        ]
        prescription_names = [item['name'] for item in selected_prescriptions_objects]

        return {
            "prescriptions_for_display": prescriptions_for_display,
            "prescription_names": prescription_names,
            "total_fee": total_fee
        }
    except Exception as e: # Catch-all for any other unexpected error in the main logic
        # It's good practice to log 'e' here for debugging (e.g., print to console or use logging module)
        # print(f"Unexpected error in load_department_prescriptions for department '{department}': {type(e).__name__} - {str(e)}")
        return {"error": f"An unexpected server error occurred while loading prescriptions. Details: {str(e)}", "prescriptions": [], "total_fee": 0}
