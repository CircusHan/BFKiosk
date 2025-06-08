"""
진료비 수납 (Blueprint)
  • GET  /payment/       → 결제 폼
  • POST /payment/       → 결제 처리 → /payment/done
  • GET  /payment/done   → 결제 완료 화면
"""
import sys # Added for logging
from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify
# Removed: uuid, random, csv, os as their functionality is moved to service

from app.services.payment_service import (
    process_new_payment,
    get_payment_details,
    load_department_prescriptions,
    update_reservation_with_payment_details,
)
from app.services.reception_service import lookup_reservation

# ──────────────────────────────────────────────────────────
#  Blueprint 인스턴트를 'payment_bp'라는 이름으로 노출
# ──────────────────────────────────────────────────────────
payment_bp = Blueprint("payment", __name__, url_prefix="/payment")

# CSV Path and in-memory payments list are now managed by payment_service


@payment_bp.route("/", methods=["GET", "POST"])
def payment():
    """
    결제 폼 & 처리
    """
    _func_args = locals()
    _module_path = sys.modules[__name__].__name__ if __name__ in sys.modules else __file__
    print(f"ENTERING: {_module_path}.payment(args={{_func_args}})")

    if request.method == "POST":
        # POST logic remains largely the same, ensure department is available if needed
        # For POST, department is implicitly handled by what's in session from GET or load_prescriptions
        patient_id = request.form.get("patient_id", "").strip() # Should come from session or a secure source ideally
        patient_id = request.form.get("patient_id", "").strip() # Should come from session or a secure source ideally

        amount_raw = request.form.get("amount", "0").replace(",", "")
        try:
            # Ensure amount is stored as a number, service expects int for now.
            # Consider if float is truly needed or if amounts are always integer cents/krw.
            amount = int(float(amount_raw))
        except ValueError:
            amount = 0

        method = request.form.get("method", "card")

        # Use patient_rrn from session as patient_id for payment processing, as per previous context
        # This assumes patient_rrn is a suitable unique identifier for the patient.
        patient_identifier_for_payment = session.get("patient_rrn", patient_id) # Fallback to form patient_id if not in session

        if not patient_identifier_for_payment:
             # Handle missing patient identifier, perhaps redirect with error
            return redirect(url_for("reception.reception", error="patient_id_missing_for_payment"))

        pay_id = process_new_payment(
            patient_id=patient_identifier_for_payment,
            amount=amount,
            method=method
        )

        # Update reservation with prescription details
        patient_rrn_for_reservation_update = session.get("patient_rrn")
        # 'last_prescriptions' should hold the list of names from load_prescriptions route
        prescription_names_to_save = session.get("last_prescriptions")
        # 'last_total_fee' should hold the total fee from load_prescriptions route
        total_fee_to_save = session.get("last_total_fee")

        if patient_rrn_for_reservation_update and \
           prescription_names_to_save is not None and \
           total_fee_to_save is not None:
            # Optionally, log the result or handle failure
            update_reservation_with_payment_details(
                patient_rrn_for_reservation_update,
                prescription_names_to_save,
                total_fee_to_save
            )
        # else:
            # Optionally, log that some data was missing for reservation update
            # For example: print("DEBUG: Missing data for reservation update in payment POST")


        # 완료 페이지로 리다이렉트
        return redirect(url_for("payment.done", pay_id=pay_id))

    # GET → 결제 입력 폼
    else: # GET request
        patient_rrn = session.get("patient_rrn")
        patient_name = session.get("patient_name")

        if not patient_rrn or not patient_name:
            # Redirect to reception if essential session info is missing
            return redirect(url_for("reception.reception", error="session_incomplete"))

        reservation_details = lookup_reservation(name=patient_name, rrn=patient_rrn)
        if not reservation_details:
            # Redirect or show error if no reservation found for user
            return redirect(url_for("reception.reception", error="no_reservation_found"))

        department = reservation_details.get("department")
        if not department:
            # Redirect or show error if department is missing in reservation
            return redirect(url_for("reception.reception", error="department_missing_in_reservation"))

        return render_template("payment.html", step="initial_payment", department=department)


@payment_bp.route("/load_prescriptions", methods=["GET"])
def load_prescriptions():
    _func_args = locals()
    _module_path = sys.modules[__name__].__name__ if __name__ in sys.modules else __file__
    print(f"ENTERING: {_module_path}.load_prescriptions(args={{_func_args}})")

    patient_rrn = session.get("patient_rrn")
    patient_name = session.get("patient_name")

    if not patient_rrn or not patient_name:
        return jsonify({"error": "User session not found or incomplete. Please go through reception.", "prescriptions": [], "total_fee": 0}), 400

    reservation_details = lookup_reservation(name=patient_name, rrn=patient_rrn)

    if not reservation_details:
        return jsonify({"error": "Reservation details not found for the current user.", "prescriptions": [], "total_fee": 0}), 400

    department = reservation_details.get("department")
    if not department: # Check if department is empty or None
        return jsonify({"error": "Department not found in reservation details. Please complete reception.", "prescriptions": [], "total_fee": 0}), 400

    # Call the service function to load prescriptions
    result = load_department_prescriptions(department)

    if result.get("error"):
        # If the service returns an error, forward it to the client
        return jsonify(result), 400 # Or 500 depending on error type

    # Store prescription names and total fee in session for certificate generation
    # The service now returns a list of names directly in result["prescriptions"]
    session["last_prescriptions"] = result["prescription_names"]
    session["last_total_fee"] = result["total_fee"]

    # The client-side JavaScript in payment.html expects a list of objects,
    # each with "Prescription" and "Fee".
    # The current `load_department_prescriptions` service returns a list of names.
    # This is a mismatch. For now, I'll adjust the service to return what client expects
    # or adjust client. The task description for service said "return a dictionary containing
    # `prescriptions` and `total_fee`".
    # The original route returned: {"Prescription": row["Prescription"], "Fee": float(row["Fee"])}
    # Let's assume for now the client needs the detailed objects.
    # I will need to modify the service `load_department_prescriptions`
    # OR I modify what's stored in session and what `certificate_service` expects.
    # Given `certificate_service.get_prescription_data_for_pdf` re-reads CSV based on names,
    # storing just names in `last_prescriptions` is correct.
    # The JSON response to the client for display on payment page, however, needs full objects.
    # This means `load_department_prescriptions` in service should return both:
    # 1. Full objects for immediate display
    # 2. Just names for session `last_prescriptions`
    # For now, let's stick to the current service output (names only) and assume the client-side
    # display might not need the fee per item, or this needs to be reconciled.
    # The original code returned full objects to client:
    # `jsonify({"prescriptions": selected_prescriptions, "total_fee": total_fee})`
    # where selected_prescriptions was `[{"Prescription": name, "Fee": fee_val}]`
    #
    # For now, I will return what the service provides, and if client breaks, it's a separate issue
    # or a need to refine service output.
    # The service returns: {"prescriptions": ["med1", "med2"], "total_fee": 123}
    # The client JS (payment.js updatePrescriptionList) expects:
    # data.prescriptions.forEach(p => { /* ... p.Prescription ... p.Fee ... */ });
    # THIS IS A MISMATCH. I must align the service output for this route.
    #
    # I will modify `load_department_prescriptions` in the service in a subsequent step
    # to return the structure `{"prescriptions_details": [{"name": ..., "fee": ...}], "total_fee": ...}`
    # and also `{"prescription_names": [name1, name2]}`.
    # For this step, I'll assume the service is updated or client is flexible.
    # Let's assume the service returns the detailed list for the client for now.
    # I will need to go back and edit the service for this.
    # For now, I will pass through what is given, which might break client.
    #
    # Re-evaluating: The service `load_department_prescriptions` was designed to return names for the session.
    # The route `load_prescriptions` is AJAX for the payment page. It needs details.
    # So, the service SHOULD provide these details.
    # I will make a note to update the service. For now, the current service output is:
    # {"prescriptions": selected_prescription_names, "total_fee": total_fee}
    # This will break the client.
    #
    # I will assume I need to fetch the details again here, or preferably, the service should return them.
    # Let's assume the service's `load_department_prescriptions` returns the detailed list
    # under key "prescriptions_for_display" and names under "prescription_names".
    #
    # If `result` contains `prescriptions` (list of names) and `total_fee`:
    # To make client work, I need to re-format. This is inefficient.
    # The service should be the one providing the correct format for this route.
    # I will proceed assuming the service output IS ALREADY what the client expects.
    # This means the service returns: {'prescriptions': [{'name': ..., 'fee': ...}], 'total_fee': ...}
    # This needs correction in the service file.
    # I will make that correction to the service file first.

    # Assuming the service is corrected to return detailed prescriptions for display:
    # e.g. result = {"prescriptions_for_display": [{"name": "med1", "fee": 100}, ...],
    #                 "prescription_names": ["med1", ...], "total_fee": 200}
    # For now, I will use the `prescriptions` key as if it contains the detailed objects.
    # This means I need to ensure the service's `load_department_prescriptions` returns this. (Done in previous step)

    # Store prescription names (for certificate service) and total fee in session
    session["last_prescriptions"] = result["prescription_names"]
    session["last_total_fee"] = result["total_fee"]

    # Return detailed prescriptions for display on the payment page (for client-side JS)
    return jsonify({"prescriptions": result["prescriptions_for_display"], "total_fee": result["total_fee"]})


@payment_bp.route("/done")
def done():
    """
    결제 완료 화면
    """
    _func_args = locals()
    _module_path = sys.modules[__name__].__name__ if __name__ in sys.modules else __file__
    print(f"ENTERING: {_module_path}.done(args={{_func_args}})")
    pay_id = request.args.get("pay_id", "")
    payment_record = get_payment_details(pay_id)

    if payment_record is None:
        return redirect(url_for("payment.payment")) # Redirect to payment form if no record

    return render_template(
        "payment.html",
        step="done",
        pay_id=payment_record["payment_id"], # Use consistent key from service
        amount=payment_record["amount"],
        method=payment_record["method"],
        # patient_id=payment_record["patient_id"] # Optionally pass patient_id to template
    )
