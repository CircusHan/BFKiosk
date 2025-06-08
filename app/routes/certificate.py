import io # Will be used for BytesIO for PDF generation
# from datetime import datetime # For filename timestamp - now handled by service
import inspect # Added for logging
import sys # Added for logging
from flask import (
    Blueprint, render_template, session, redirect, url_for, Response
)
from werkzeug.http import dump_options_header # Added for Content-Disposition
from urllib.parse import quote
# Removed: request, jsonify as they are not used after refactoring
# Removed: os, csv, random as their functionality is moved to service

from app.utils.pdf_generator import MissingKoreanFontError # Keep this for error handling
# The actual PDF generation functions (create_prescription_pdf_bytes, create_confirmation_pdf_bytes)
# are now called by the service, so direct import might not be needed here.
# However, MissingKoreanFontError is caught here.

from app.services.certificate_service import (
    get_prescription_data_for_pdf,
    prepare_prescription_pdf,
    prepare_medical_confirmation_pdf,
)
from app.services.reception_service import lookup_reservation

certificate_bp = Blueprint(
    "certificate", __name__, url_prefix="/certificate", template_folder="../../templates"
)

# Data Paths and _load_prescription_data removed as they are handled by the service


@certificate_bp.route("/", methods=["GET"])
def certificate():
    """
    Renders the main certificate choice page.
    """
    _func_args = locals()
    _module_path = sys.modules[__name__].__name__ if __name__ in sys.modules else __file__
    print(f"ENTERING: {_module_path}.certificate(args={{_func_args}})")
    return render_template("certificate.html")


@certificate_bp.route("/prescription/", methods=["GET"])
def generate_prescription_pdf():
    """
    Generates a prescription PDF.
    """
    _func_args = locals()
    _module_path = sys.modules[__name__].__name__ if __name__ in sys.modules else __file__
    print(f"ENTERING: {_module_path}.generate_prescription_pdf(args={{_func_args}})")
    patient_name = session.get("patient_name")
    patient_rrn = session.get("patient_rrn")
    # department = session.get("department") # Removed

    if not all([patient_name, patient_rrn]):
        return redirect(url_for("reception.reception", error="patient_info_missing"))

    # if not department: # Removed old check
    #     return redirect(url_for("reception.reception", error="department_info_missing"))

    reservation_details = lookup_reservation(name=patient_name, rrn=patient_rrn)

    if not reservation_details:
        # Redirect or return error if no reservation found for the user
        return redirect(url_for("reception.reception", error="no_reservation_for_pdf"))

    department = reservation_details.get("department")
    if not department: # Check if department is empty or None in the fetched details
        # Redirect or return error if department is missing in the reservation
        return redirect(url_for("reception.reception", error="department_missing_for_pdf"))

    # last_prescriptions_from_session = session.get("last_prescriptions") # Removed
    # last_total_fee_from_session = session.get("last_total_fee") # Removed

    # The service function get_prescription_data_for_pdf now expects patient_rrn and department.
    # It will fetch prescription details from reservations.csv.
    # if last_prescriptions_from_session is None or last_total_fee_from_session is None: # Removed block
    #     return redirect(url_for("payment.payment", error="prescription_data_missing_from_session"))

    status_code, result_payload = get_prescription_data_for_pdf(
        patient_rrn=patient_rrn,
        department=department
    )

    if status_code == "OK":
        prescription_details = result_payload # This is the actual data dictionary
        try:
            pdf_bytes, filename = prepare_prescription_pdf(
                patient_name=patient_name,
                patient_rrn=patient_rrn,
                department=department, # department is still available from session/initial check
                prescription_details=prescription_details
            )
            if pdf_bytes is None:
                # This specific error indicates a failure within prepare_prescription_pdf itself,
                # not necessarily an issue with data fetching (which status_code would have caught).
                return render_template("error.html", message="PDF 생성 중 내부 오류가 발생했습니다. (Prepare stage)"), 500

        except MissingKoreanFontError as e:
            return render_template("error.html", message=str(e)), 500

        disposition = f"inline; filename*=UTF-8''{quote(filename)}"
        return Response(
            pdf_bytes,
            mimetype='application/pdf',
            headers={'Content-Disposition': disposition}
        )
    # Handle error cases based on status_code from get_prescription_data_for_pdf
    elif status_code == "NEEDS_RECEPTION_COMPLETION": # New condition
        return render_template("error.html", message=result_payload), 400
    elif status_code in ["NEEDS_PAYMENT", "ZERO_FEE_PAID"]:
        # These are client-side correctable or informational errors
        return render_template("error.html", message=result_payload), 400
    elif status_code in ["NOT_FOUND", "FILE_NOT_FOUND", "DATA_ERROR"]:
        # These are server-side or data integrity issues
        return render_template("error.html", message=result_payload), 500
    else:
        # Catch-all for any other unexpected status codes from the service
        return render_template("error.html", message="알 수 없는 오류가 발생했습니다. 관리자에게 문의하세요."), 500

    # session.pop("last_prescriptions", None) # Removed
    # session.pop("last_total_fee", None) # Removed
    # This part is unreachable due to the if/elif/else structure covering all status_code paths.
    # The try/except for PDF generation is now within the "OK" block.


@certificate_bp.route("/medical_confirmation/", methods=["GET"])
def generate_confirmation_pdf():
    """
    Generates a medical confirmation PDF.
    """
    _func_args = locals()
    _module_path = sys.modules[__name__].__name__ if __name__ in sys.modules else __file__
    print(f"ENTERING: {_module_path}.generate_confirmation_pdf(args={{_func_args}})")
    patient_name = session.get("patient_name")
    patient_rrn = session.get("patient_rrn")
    # department = session.get("department") # Removed

    if not all([patient_name, patient_rrn]):
        return redirect(url_for("reception.reception", error="patient_info_missing"))

    # if not department: # Removed old check
    #     return redirect(url_for("reception.reception", error="department_info_missing_for_confirmation"))

    reservation_details = lookup_reservation(name=patient_name, rrn=patient_rrn)

    if not reservation_details:
        # Redirect or return error if no reservation found for the user
        return redirect(url_for("reception.reception", error="no_reservation_for_confirmation_pdf"))

    department_as_disease_name = reservation_details.get("department")
    if not department_as_disease_name: # Check if department is empty or None
        # Redirect or return error if department is missing in the reservation
        return redirect(url_for("reception.reception", error="department_missing_for_confirmation_pdf"))

    try:
        pdf_bytes, filename = prepare_medical_confirmation_pdf(
            patient_name=patient_name,
            patient_rrn=patient_rrn,
            disease_name=department_as_disease_name # Use the fetched department here
        )
        if pdf_bytes is None: # If service function couldn't generate PDF
             return render_template("error.html", message="Could not generate confirmation PDF."), 500

    except MissingKoreanFontError as e:
        return render_template("error.html", message=str(e)), 500

    disposition = f"inline; filename*=UTF-8''{quote(filename)}"
    return Response(
        pdf_bytes, # pdf_bytes is already BytesIO object from service
        mimetype='application/pdf',
        headers={'Content-Disposition': disposition}
    )
