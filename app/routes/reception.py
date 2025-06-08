# app/routes/reception.py
from flask import Blueprint, render_template, request, session

# Import service functions and SYMPTOMS list
from app.services.reception_service import (
    handle_scan_action,
    handle_manual_action,
    handle_choose_symptom_action,
    SYMPTOMS  # SYMPTOMS is imported for use in the template
)

reception_bp = Blueprint('reception', __name__, url_prefix="/reception", template_folder='../../templates')
# Note: Added url_prefix="/reception" for consistency if other blueprints have it.
# Original did not have url_prefix for the blueprint itself, but relied on @reception_bp.route("/reception").
# This change makes routes like /reception/ instead of just /reception.
# If the old style /reception is required, the route below should be @reception_bp.route("/", methods=["GET", "POST"])
# and the blueprint registration should be Blueprint('reception', __name__, template_folder='../../templates')

# Definitions of BASE_DIR, RESV_CSV, SYMPTOMS, SYM_TO_DEPT, fake_scan_rrn,
# lookup_reservation, new_ticket are removed as they are now in the service.

@reception_bp.route("/", methods=["GET", "POST"]) # Changed to "/" assuming url_prefix handles /reception
def reception():
    if request.method == "POST":
        action = request.form.get("action")

        # 1) 주민등록증 인식 ---------------------------------------------------
        if action == "scan":
            scan_result = handle_scan_action() # Service returns dict with name, rrn, reservation_details
            session['patient_name'] = scan_result["name"]
            session['patient_rrn'] = scan_result["rrn"]

            if scan_result["reservation_details"]:
                return render_template("reception.html", step="reserved",
                                       name=scan_result["name"], **scan_result["reservation_details"])
            else:
                return render_template("reception.html", step="symptom",
                                       name=scan_result["name"], rrn=scan_result["rrn"], symptoms=SYMPTOMS)

        # 2) 개인정보 직접 입력 ------------------------------------------------
        elif action == "manual":
            name = request.form.get("name", "").strip()
            rrn  = request.form.get("rrn",  "").strip()

            if not name or not rrn:
                return render_template("reception.html", step="input",
                                       err="이름과 주민번호를 모두 입력하세요.") # symptoms=SYMPTOMS might be needed if form is re-shown

            session['patient_name'] = name
            session['patient_rrn'] = rrn

            reservation_details = handle_manual_action(name, rrn) # Service returns dict or None

            if reservation_details:
                return render_template("reception.html", step="reserved",
                                       name=name, **reservation_details)
            else:
                return render_template("reception.html", step="symptom",
                                       name=name, rrn=rrn, symptoms=SYMPTOMS)

        # 3) 증상 선택 후 번호표 발급 ----------------------------------------
        elif action == "choose_symptom":
            symptom_key = request.form.get("symptom") # This will be "fever", "cough" etc.

            # Ensure patient name and rrn are in session from previous step
            if 'patient_name' not in session or 'patient_rrn' not in session:
                # Redirect to initial step if patient info is missing
                return redirect(url_for("reception.reception"))


            symptom_result = handle_choose_symptom_action(symptom_key) # Returns dict with department, ticket

            session["department"] = symptom_result["department"]
            session["ticket"] = symptom_result["ticket"]

            # Pass patient name to the ticket step as well, if needed by template
            patient_name = session.get("patient_name", "")

            return render_template("reception.html", step="ticket",
                                   department=symptom_result["department"],
                                   ticket=symptom_result["ticket"],
                                   name=patient_name) # Added name here

    # GET → 접수 방법 선택
    return render_template("reception.html", step="method")
