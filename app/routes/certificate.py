import io # Will be used for BytesIO for PDF generation
# from datetime import datetime # For filename timestamp - now handled by service
import inspect # Added for logging
import sys # Added for logging
from flask import (
    Blueprint, render_template, session, redirect, url_for, Response
)
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
    department = session.get("department")

    if not all([patient_name, patient_rrn]):
        return redirect(url_for("reception.reception", error="patient_info_missing"))

    if not department:
        return redirect(url_for("reception.reception", error="department_info_missing"))

    # last_prescriptions_from_session = session.get("last_prescriptions") # Removed
    # last_total_fee_from_session = session.get("last_total_fee") # Removed

    # The service function get_prescription_data_for_pdf now expects patient_rrn and department.
    # It will fetch prescription details from reservations.csv.
    # if last_prescriptions_from_session is None or last_total_fee_from_session is None: # Removed block
    #     return redirect(url_for("payment.payment", error="prescription_data_missing_from_session"))

    prescription_details = get_prescription_data_for_pdf(
        patient_rrn=patient_rrn, # Changed
        department=department  # Changed
    )

    if not prescription_details:
        # This case handles if get_prescription_data_for_pdf returns None
        # (e.g., patient not in reservations.csv, CSV error in service, or no prescription files)
        # Redirecting to reception or a generic error page might be more appropriate
        # than payment, as payment data might not be the issue anymore.
        # For now, keeping the error message generic.
        return render_template("error.html", message="진료확인서 발급에 필요한 처방 상세 정보를 불러오지 못했습니다. 해당 환자의 예약 정보 또는 처방전 데이터 파일을 확인해주세요."), 500
        # Previous redirect: url_for("payment.payment", error="failed_to_load_prescription_details")

    # session.pop("last_prescriptions", None) # Removed
    # session.pop("last_total_fee", None) # Removed

    try:
        pdf_bytes, filename = prepare_prescription_pdf(
            patient_name=patient_name,
            patient_rrn=patient_rrn,
            department=department,
            prescription_details=prescription_details
        )
        if pdf_bytes is None: # If service function couldn't generate PDF
            return render_template("error.html", message="Could not generate prescription PDF."), 500

    except MissingKoreanFontError as e:
        return render_template("error.html", message=str(e)), 500

    return Response(
        pdf_bytes, # pdf_bytes is already BytesIO object from service
        mimetype='application/pdf',
        headers={'Content-Disposition': f'inline;filename={filename}'}
    )


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
    department = session.get("department") # Used as "병명" (diagnosis/reason for visit)

    if not all([patient_name, patient_rrn]):
        return redirect(url_for("reception.reception", error="patient_info_missing"))

    if not department: # Department is essential for "병명"
        return redirect(url_for("reception.reception", error="department_info_missing_for_confirmation"))

    try:
        pdf_bytes, filename = prepare_medical_confirmation_pdf(
            patient_name=patient_name,
            patient_rrn=patient_rrn,
            disease_name=department # department is used as disease_name
        )
        if pdf_bytes is None: # If service function couldn't generate PDF
             return render_template("error.html", message="Could not generate confirmation PDF."), 500

    except MissingKoreanFontError as e:
        return render_template("error.html", message=str(e)), 500

    return Response(
        pdf_bytes, # pdf_bytes is already BytesIO object from service
        mimetype='application/pdf',
        headers={'Content-Disposition': f'inline;filename={filename}'}
    )
