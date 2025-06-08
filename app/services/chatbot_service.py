import os
import base64
import google.generativeai as genai
import sys # Added for logging
import json # Added for JSON parsing
import traceback # Added for stack trace logging
# import io # Not strictly needed for current logic but good for future image manipulation

from app.services.reception_service import (
    lookup_reservation,
    SYMPTOMS,
    SYM_TO_DEPT,
    handle_choose_symptom_action,
    # add_new_patient_reception, # Removed as per new logic
    new_ticket, # Added
    update_reservation_status, # Added
    # fake_scan_rrn # Not using fake_scan_rrn in this path for now
)
from app.services.payment_service import (
    load_department_prescriptions,
    update_reservation_with_payment_details
)
from app.services.certificate_service import (
    get_prescription_data_for_pdf,
    prepare_prescription_pdf,
    prepare_medical_confirmation_pdf
)
from app.utils.pdf_generator import MissingKoreanFontError
# base64 is already imported at the top of the file, so no need to re-import here.

# Corrected SYSTEM_INSTRUCTION_PROMPT based on original chatbot.py
SYSTEM_INSTRUCTION_PROMPT = """당신은 대한민국 공공 보건소의 친절하고 유능한 AI 안내원 '늘봄이'입니다. 당신의 임무는 사용자의 요청을 이해하고, 적절한 서비스로 안내하거나 일반적인 질문에 답변하는 것입니다.

**주요 작업:**

1.  **의도 파악:** 사용자의 요청이 일반 문의인지 또는 특정 서비스 요청인지 식별합니다.
    *   서비스 종류: "접수 (Reception)", "수납 (Payment)", "증명서 발급 (Certificate Issuance)"

2.  **파라미터 추출 (서비스 요청 시):** 사용자의 메시지에서 다음 정보를 추출합니다. 모든 파라미터는 선택 사항이며, 사용자가 언급한 경우에만 포함합니다.
    *   `name` (문자열, 예: "홍길동")
    *   `rrn` (문자열, 주민등록번호, 형식: xxxxxx-xxxxxxx, 예: "900101-1234567")
    *   `symptom` (문자열, 예: "두통", "기침", "감기", 가능한 경우 미리 정의된 목록 사용) - 접수 시에만 해당
    *   `department` (문자열, 예: "내과", "소아과") - 사용자가 특정 부서를 언급한 경우
    *   `time` (문자열, 예약 시간, 예: "오늘 오후 2시", "내일 오전 10시 30분") - 접수 시 사용자가 언급한 경우
    *   `location` (문자열, 예약 희망 위치 또는 특정 클리닉 명칭, 예: "본원", "강남지점 피부과") - 접수 시 사용자가 언급한 경우
    *   `doctor` (문자열, 담당 의사 이름, 예: "김민준 의사") - 접수 시 사용자가 언급한 경우
    *   `certificate_type` (다음 중 하나: "prescription" (처방전), "confirmation" (진료확인서)) - 증명서 발급 시에만 해당
    *   `payment_stage` (다음 중 하나: "initial" (결제 시작), "confirmation" (결제 수단 확인)) - 수납 시에만 해당
    *   `payment_method` (다음 중 하나: "cash" (현금), "card" (카드)) - 수납 확인(confirmation) 단계에서만 해당

3.  **JSON 응답 형식 (서비스 요청 시):** 서비스 요청의 경우, 다음과 같은 JSON 형식으로 응답해야 합니다.
    ```json
    {
      "intent": "reception" | "payment" | "certificate" | "general",
      "parameters": {
        "name": "...",
        "rrn": "...",
        "symptom": "...",
        "department": "...",
        "time": "...",
        "location": "...",
        "doctor": "...",
        "certificate_type": "...",
        "payment_stage": "...",
        "payment_method": "..."
      },
      "user_query": "사용자의 원본 메시지 전체"
    }
    ```
    *   `intent`는 식별된 서비스 또는 "general"로 설정합니다.
    *   `parameters` 객체에는 추출된 정보만 포함합니다. 값이 없는 파라미터는 생략합니다.
    *   `user_query`에는 사용자의 원본 메시지를 그대로 전달합니다.
    **중요: 응답은 반드시 JSON 객체 문자열 그 자체여야 합니다. JSON 객체를 설명하는 어떤 추가적인 텍스트나 마크다운 형식(예: ```json ... ```)도 포함해서는 안 됩니다. 오직 순수한 JSON 문자열만 응답으로 제공해야 합니다.**

4.  **JSON 응답 형식 (일반 문의 시):** 사용자의 요청이 특정 서비스와 관련 없는 일반 문의인 경우, 다음과 같은 JSON 형식으로 응답해야 합니다.
    ```json
    {
      "intent": "general",
      "reply": "늘봄이가 제공하는 일반적인 답변입니다."
    }
    ```
    *   `reply` 필드에 직접적인 텍스트 답변을 제공합니다.
    **중요: 이 경우에도 응답은 위의 JSON 형식이어야 하며, `reply` 값 외에 다른 설명이나 추가 텍스트를 포함하지 마십시오.**

**세부 지침:**

*   **언어:** 모든 답변은 한국어로 제공합니다.
*   **챗봇 이름:** 당신의 이름은 '늘봄이'입니다.
*   **정보 요청 (누락 시):**
    *   **접수:** `name` 또는 `rrn`이 제공되지 않으면, 정중하게 요청합니다. (예: "접수를 위해 성함과 주민등록번호를 말씀해주시겠어요?")
    *   **수납:** 진료 기록 조회 등을 위해 `name` 또는 `rrn`이 필요하다고 판단되면, 정중하게 요청합니다. (예: "수납 처리를 위해 성함이나 주민등록번호를 알려주시겠어요?")
*   **수납 단계 (Payment Stage):**
    *   사용자가 처음 수납을 요청하면 `payment_stage`를 "initial"로 설정합니다.
    *   사용자가 결제 수단(현금, 카드 등)을 언급하며 확인을 요청하면 `payment_stage`를 "confirmation"으로 설정하고 `payment_method`를 추출합니다. 예를 들어, 사용자가 현금으로 결제하겠다고 말하면, 이는 `payment_stage`가 "confirmation"으로 변경되고 `payment_method`가 "cash"로 설정됨을 의미합니다. **이때, 이전 단계에서 안내된 `total_fee` (총액) 및 `prescription_names` (처방약 목록)을 사용자가 다시 언급하거나 확인하는 경우, 해당 정보도 함께 추출하도록 노력해야 합니다.**
*   **개인정보 보호:**
    *   개인적인 의학적 진단이나 처방은 제공하지 않으며, "의사 또는 전문 의료인과 상담하시는 것이 가장 좋습니다."와 같이 안내합니다.
    *   수집된 개인정보는 해당 서비스 처리 목적으로만 사용됨을 명시할 수 있습니다 (필요시).
*   **응답 스타일:**
    *   항상 친절하고 공손한 태도를 유지합니다.
    *   명확하고 간결하며 이해하기 쉽게 답변합니다.
    *   긍정적이고 따뜻한 어조를 사용합니다.
    *   전문 용어 사용을 피하고, 쉬운 단어로 설명합니다.

**예시 시나리오:**

*   사용자: "안녕하세요, 오늘 진료 접수하고 싶어요."
    늘봄이 (JSON):
    ```json
    {
      "intent": "reception",
      "parameters": {},
      "user_query": "안녕하세요, 오늘 진료 접수하고 싶어요."
    }
    ```
    늘봄이 (후속 질문): "네, 안녕하세요! 접수를 도와드릴게요. 성함과 주민등록번호를 말씀해주시겠어요?"

*   사용자: "머리가 아파서 왔는데, 홍길동이고 주민번호는 900101-1234567입니다."
    늘봄이 (JSON):
    ```json
    {
      "intent": "reception",
      "parameters": {
        "name": "홍길동",
        "rrn": "900101-1234567",
        "symptom": "머리가 아픔"
      },
      "user_query": "머리가 아파서 왔는데, 홍길동이고 주민번호는 900101-1234567입니다."
    }
    ```

*   사용자: "진료비 수납하려고요. 이름은 고길동, 주민번호는 850515-1987654 입니다."
    늘봄이 (JSON):
    ```json
    {
      "intent": "payment",
      "parameters": {
        "name": "고길동",
        "rrn": "850515-1987654",
        "payment_stage": "initial"
      },
      "user_query": "진료비 수납하려고요. 이름은 고길동, 주민번호는 850515-1987654 입니다."
    }
    ```

*   사용자: "네, 카드로 결제할게요. 금액은 35000원이고, 처방약은 감기약, 소화제 맞아요." (이전 대화에서 수납 의도, 사용자 정보, 처방내역 및 총액이 안내된 상태)
    늘봄이 (JSON):
    ```json
    {
      "intent": "payment",
      "parameters": {
        "name": "고길동",
        "rrn": "850515-1987654",
        "payment_stage": "confirmation",
        "payment_method": "card",
        "total_fee": "35000",
        "prescription_names": ["감기약", "소화제"]
      },
      "user_query": "네, 카드로 결제할게요. 금액은 35000원이고, 처방약은 감기약, 소화제 맞아요."
    }
    ```
*   사용자: "네, 카드로 결제할게요. 
    늘봄이 (JSON):
    ```json
    {
      "intent": "payment",
      "parameters": {
        "name": "고길동",
        "rrn": "850515-1987654",
        "payment_stage": "confirmation",
        "payment_method": "card",
      },
      "user_query": "네, 카드로 결제할게요."
    }
    ```
*   사용자: "네, 현금으로 결제할게요. 
    늘봄이 (JSON):
    ```json
    {
      "intent": "payment",
      "parameters": {
        "name": "고길동",
        "rrn": "850515-1987654",
        "payment_stage": "confirmation",
        "payment_method": "cash",
      },
      "user_query": "네, 현금으로 결제할게요."
    }
    ```
    
*   사용자: "처방전 발급해주세요."
    늘봄이 (JSON):
    ```json
    {
      "intent": "certificate",
      "parameters": {
        "certificate_type": "prescription"
      },
      "user_query": "처방전 발급해주세요."
    }
    ```

*   사용자: "오늘 보건소 운영시간 알려줘."
    늘봄이 (JSON):
    ```json
    {
      "intent": "general",
      "reply": "네, 늘봄이가 알려드릴게요. 저희 보건소는 평일 오전 9시부터 오후 6시까지 운영합니다. 점심시간은 12시부터 1시까지입니다."
    }
    ```

이제 사용자의 요청에 따라 위 지침을 정확히 준수하여 응답해주세요."""

# Placeholder functions for handling specific intents
def handle_reception_request(parameters: dict, user_query: str) -> dict:
    _func_args = locals()
    _module_path = sys.modules[__name__].__name__ if __name__ in sys.modules else __file__
    print(f"ENTERING: {_module_path}.handle_reception_request(args={{_func_args}})")

    name = parameters.get("name")
    rrn = parameters.get("rrn")
    symptom_param = parameters.get("symptom") # This might be a display name or a key
    # time_param, location_param, doctor_param removed from here as they are not used for saving.

    if not name or not rrn:
        # This should ideally be caught by Gemini's prompting, but as a fallback.
        return {"reply": "접수를 위해 성함과 주민등록번호를 알려주시겠어요? 예: 홍길동, 123456-1234567"}

    reservation_details = lookup_reservation(name, rrn)

    if reservation_details:
        status = reservation_details.get("status")
        dept = reservation_details.get("department", "알 수 없음")
        ticket = reservation_details.get("ticket_number", "알 수 없음")
        time_from_csv = reservation_details.get("time")
        location_from_csv = reservation_details.get("location")
        doctor_from_csv = reservation_details.get("doctor")

        if status == "Registered":
            reply_message = f"{name}님은 이미 {dept}으로 접수되셨습니다. 대기번호는 {ticket}번 입니다."
            if time_from_csv and time_from_csv.strip():
                reply_message += f" 예약 시간: {time_from_csv}."
            if location_from_csv and location_from_csv.strip():
                reply_message += f" 위치: {location_from_csv}."
            if doctor_from_csv and doctor_from_csv.strip():
                reply_message += f" 담당 의사: {doctor_from_csv}."
            reply_message += " 추가 문의가 있으신가요?"
            return {"reply": reply_message}
        elif status == "Paid":
            return {"reply": f"{name}님은 이미 진료를 마치고 수납까지 완료하셨습니다. 증명서 발급이 필요하시면 말씀해주세요."}
        elif status == "Cancelled":
            return {"reply": f"{name}님의 이전 예약은 취소된 것으로 확인됩니다. 새로 접수하시겠습니까?"} # Could offer to re-register
        elif status == "Pending":
            pending_department = reservation_details.get("department")
            patient_name = reservation_details.get("name", name) # Use name from record, fallback to param
            patient_rrn = reservation_details.get("rrn", rrn)   # Use RRN from record
            final_department = pending_department

            if not pending_department:
                symptom_from_params = parameters.get("symptom") # Check if symptom was provided in this turn
                if not symptom_from_params:
                    available_symptoms_text = ", ".join([s[1] for s in SYMPTOMS])
                    return {"reply": f"{patient_name}님의 예약은 확인되었으나, 진료 부서가 지정되지 않았습니다. 어떤 증상으로 방문하셨나요? 예: {available_symptoms_text}"}

                symptom_key = None
                if symptom_from_params in SYM_TO_DEPT:
                    symptom_key = symptom_from_params
                else:
                    for key_val, display_name_val in SYMPTOMS:
                        if symptom_from_params == display_name_val:
                            symptom_key = key_val
                            break
                if not symptom_key:
                    available_symptoms_text = ", ".join([s[1] for s in SYMPTOMS])
                    return {"reply": f"선택하신 '{symptom_from_params}' 증상을 찾을 수 없습니다. 다음 증상 중에서 선택해주세요: {available_symptoms_text}"}

                symptom_action_result = handle_choose_symptom_action(symptom_key)
                final_department = symptom_action_result["department"]

            if not final_department : # Should ideally be resolved by now, but as a safeguard
                 return {"reply": f"{patient_name}님, 예약 처리를 위해 진료 부서 정보가 필요합니다. 증상을 말씀해주시겠어요?"}

            new_ticket_number = new_ticket(final_department)

            update_kwargs = {
                'department': final_department,
                'ticket_number': new_ticket_number,
                'name': patient_name
                # time, location, doctor are not saved via this function call directly.
                # They are assumed to be part of the reservation_details if set initially.
            }
            update_success = update_reservation_status(patient_rrn, 'Registered', **update_kwargs)

            if update_success:
                base_reply = f"{patient_name}님의 예약이 확인되었습니다. {final_department}으로 접수되었으며, 대기번호는 {new_ticket_number}번입니다."
                # Display time/location/doctor if they were part of the original 'Pending' reservation_details
                time_val = reservation_details.get("time")
                loc_val = reservation_details.get("location")
                doc_val = reservation_details.get("doctor")

                if time_val and time_val.strip():
                    base_reply += f" 예약 시간: {time_val}."
                if loc_val and loc_val.strip():
                    base_reply += f" 위치: {loc_val}."
                if doc_val and doc_val.strip():
                    base_reply += f" 담당 의사: {doc_val}."
                return {"reply": base_reply}
            else:
                return {"error": "예약 상태 업데이트 중 오류가 발생했습니다. 데스크에 문의해주세요.", "status_code": 500}
        else:
            # Catch any other non-handled statuses
            return {"reply": f"{name}님의 예약 상태는 '{status}'입니다. 현재 새로 접수할 수 없거나 다른 조치가 필요합니다. 데스크에 문의해주세요."}
    else: # No existing reservation, patient not found in reservations.csv
        return {"reply": f"죄송합니다, {name}님의 정보를 시스템에서 찾을 수 없습니다. 데스크에 문의하여 등록을 먼저 진행해주시기 바랍니다."}

def handle_payment_request(parameters: dict, user_query: str) -> dict:
    _func_args = locals()
    _module_path = sys.modules[__name__].__name__ if __name__ in sys.modules else __file__
    print(f"ENTERING: {_module_path}.handle_payment_request(args={{_func_args}})")

    name = parameters.get("name")
    rrn = parameters.get("rrn")
    payment_stage = parameters.get("payment_stage") # "initial" or "confirmation"
    payment_method = parameters.get("payment_method") # "cash" or "card"

    # These might be passed by Gemini in the confirmation stage from context
    # Ensure they are retrieved here, as they are top-level in 'parameters' from Gemini
    retrieved_total_fee_str = parameters.get("total_fee")
    retrieved_prescription_names = parameters.get("prescription_names")


    if not name or not rrn:
        return {"reply": "수납을 진행하시려면 성함과 주민등록번호를 알려주세요. 예: 홍길동, 123456-1234567"}

    reservation_details = lookup_reservation(name, rrn)

    if not reservation_details:
        return {"reply": "등록된 예약 정보를 찾을 수 없습니다. 먼저 접수를 진행해주세요."}

    status = reservation_details.get("status")
    department = reservation_details.get("department")

    if not department:
        return {"error": "환자의 부서 정보가 예약에 없어 수납 처리를 진행할 수 없습니다.", "status_code": 500}

    if status == "Paid":
        return {"reply": f"{name}님은 이미 수납을 완료하셨습니다."}
    if status == "Pending":
        return {"reply": "아직 접수가 완료되지 않았습니다. 먼저 접수를 완료해주세요."}
    if status != "Registered":
         return {"reply": f"{name}님의 현재 예약 상태('{status}')에서는 수납을 진행할 수 없습니다. 도움이 필요하시면 데스크에 문의해주세요."}

    if payment_stage == "initial":
        try:
            prescription_info = load_department_prescriptions(department)
            if prescription_info.get("error"):
                return {"reply": f"처방 정보를 불러오는 중 오류가 발생했습니다: {prescription_info['error']}"}

            # Correctly get the list of detailed prescription objects
            detailed_prescriptions = prescription_info.get("prescriptions_for_display", [])

            # Format the prescriptions for display.
            # This relies on payment_service.load_department_prescriptions correctly providing 'name' and 'fee'
            # in the dictionaries within the 'prescriptions_for_display' list.
            formatted_prescriptions = "\n".join([f"- {item['name']}: {item['fee']}원" for item in detailed_prescriptions])

            # Get other necessary info from prescription_info
            actual_prescription_names = prescription_info.get("prescription_names", [])
            total_fee = prescription_info.get("total_fee")

            if total_fee is None: # Keep existing check for total_fee
                 return {"error": "처방 정보에서 총 금액을 가져올 수 없습니다.", "status_code": 500}

            reply_message = (
                f"{name}님의 처방 내역입니다:\n{formatted_prescriptions}\n"
                f"총 금액은 {total_fee}원 입니다. "
                "현금으로 결제하시겠습니까, 아니면 카드로 결제하시겠습니까?"
            )
            # Gemini needs to be prompted to remember/extract 'total_fee' and 'prescription_names' for the 'confirmation' stage.
            # The actual_prescription_names (list of strings) and total_fee (number) are what need to be passed back.
            return {"reply": reply_message}

        except Exception as e:
            print(f"Error in payment_stage 'initial' for patient {name} (RRN: {rrn}):")
            traceback.print_exc() # This prints the full traceback to stderr
            return {"error": "처방 정보 조회 중 예기치 않은 오류가 발생했습니다.", "status_code": 500}

    elif payment_stage == "confirmation":
        print("confirmation mode")
        if not payment_method:
            return {"reply": "결제 수단을 말씀해주세요 (예: 현금 또는 카드)."}
        if payment_method not in ["cash", "card"]:
            return {"reply": "유효한 결제 수단이 아닙니다. '현금' 또는 '카드'로 말씀해주세요."}

    
        # Optional: Validate AI extracted parameters against actual data if needed.
        # For now, we will trust the re-fetched data as the source of truth.
        # The variables retrieved_total_fee_str and retrieved_prescription_names from parameters are no longer used directly for processing.

        prescription_info = load_department_prescriptions(department)
        if prescription_info.get("error"):
            return {"reply": f"처방 정보를 불러오는 중 오류가 발생했습니다: {prescription_info['error']}"}

        print(prescription_info)

        
        # Correctly get the list of detailed prescription objects
        detailed_prescriptions = prescription_info.get("prescriptions_for_display", [])

        # Format the prescriptions for display.
        # This relies on payment_service.load_department_prescriptions correctly providing 'name' and 'fee'
        # in the dictionaries within the 'prescriptions_for_display' list.
        formatted_prescriptions = "\n".join([f"- {item['name']}: {item['fee']}원" for item in detailed_prescriptions])

        # Get other necessary info from prescription_info
        actual_prescription_names = prescription_info.get("prescription_names", [])
        actual_total_fee = prescription_info.get("total_fee")

        try:
            # Ensure actual_total_fee is an int, though it should be from load_department_prescriptions
            if not isinstance(actual_total_fee, int):
                 actual_total_fee = int(actual_total_fee)

            success = update_reservation_with_payment_details(rrn, actual_prescription_names, actual_total_fee)

            if success:
                return {"reply": f"{name}님의 결제가 {payment_method}로 완료되었습니다. 총 {actual_total_fee}원이 결제되었습니다. 감사합니다."}
            else:
                return {"error": "결제 처리 중 내부 오류가 발생했습니다. 다시 시도해주시거나 데스크에 문의하세요.", "status_code": 500}
        except Exception as e:
            print(f"Error in payment_stage 'confirmation' for {name} ({rrn}): {e}")
            return {"error": "결제 확인 처리 중 예기치 않은 오류가 발생했습니다.", "status_code": 500}

    else:
        return {"error": f"알 수 없는 결제 단계(payment_stage)입니다: '{payment_stage}'.", "status_code": 400}

def handle_certificate_request(parameters: dict, user_query: str) -> dict:
    _func_args = locals()
    _module_path = sys.modules[__name__].__name__ if __name__ in sys.modules else __file__
    print(f"ENTERING: {_module_path}.handle_certificate_request(args={{_func_args}})")

    name = parameters.get("name")
    rrn = parameters.get("rrn")
    certificate_type = parameters.get("certificate_type") # "prescription" or "confirmation"

    if not name or not rrn:
        return {"reply": "증명서 발급을 위해 성함과 주민등록번호를 알려주세요. 예: 홍길동, 123456-1234567"}

    if not certificate_type:
        # This case should ideally be handled by Gemini's parameter extraction or prompting logic.
        # If certificate_type is missing, Gemini should have asked for it based on the system prompt.
        return {"reply": "발급받으실 증명서 종류를 말씀해주세요. '처방전' 또는 '진료확인서' 중에서 선택할 수 있습니다."}

    reservation_details = lookup_reservation(name, rrn)

    if not reservation_details:
        return {"reply": "등록된 예약 정보를 찾을 수 없습니다. 증명서 발급을 위해서는 접수 및 진료, 수납이 완료되어야 합니다."}

    status = reservation_details.get("status")
    # Department is needed for prescription, and used as disease_name for confirmation.
    department = reservation_details.get("department")

    if not department: # Should not happen if patient has gone through reception/payment
        return {"error": "환자의 부서 정보가 없어 증명서 발급을 진행할 수 없습니다.", "status_code": 500}

    try:
        if certificate_type == "prescription":
            # get_prescription_data_for_pdf itself checks if status is "Paid"
            # and if prescription_names and total_fee exist.
            status_code_or_ok, data = get_prescription_data_for_pdf(rrn, department)

            if status_code_or_ok != "OK":
                # 'data' contains the user-friendly error message from get_prescription_data_for_pdf
                return {"reply": f"처방전을 발급할 수 없습니다: {data}"}

            prescription_pdf_data = data # This is the dict with items and total_fee
            pdf_bytes, filename = prepare_prescription_pdf(name, rrn, department, prescription_pdf_data)

            if pdf_bytes and filename:
                pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
                return {
                    "reply": f"{name}님의 처방전 발급이 완료되었습니다. 새 창에서 확인해주세요.",
                    "pdf_filename": filename,
                    "pdf_data_base64": pdf_base64  # For the API to send to client
                }
            else: # Should ideally not happen if prepare_prescription_pdf is robust
                return {"reply": "처방전 PDF 생성 중 예상치 못한 오류가 발생했습니다."}

        elif certificate_type == "confirmation":
            # Explicit status check for medical confirmation certificate.
            if status != "Paid":
                error_message = "진료확인서를 발급받으려면 먼저 수납을 완료해주세요."
                if status == "Pending": # Still at reception, not even seen by doctor
                    error_message = "진료확인서를 발급받으려면 먼저 접수를 완료하고 진료 및 수납을 진행해주세요."
                elif status == "Registered": # Seen by doctor, but not paid yet
                    error_message = "진료확인서를 발급받으려면 먼저 진료 후 수납을 완료해주세요."
                return {"reply": error_message}

            # Using department as disease_name for simplicity as per original structure.
            # In a real system, disease_name would come from medical records.
            pdf_bytes, filename = prepare_medical_confirmation_pdf(name, rrn, department)

            if pdf_bytes and filename:
                pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
                return {
                    "reply": f"{name}님의 진료확인서 발급이 완료되었습니다. 새 창에서 확인해주세요.",
                    "pdf_filename": filename,
                    "pdf_data_base64": pdf_base64 # For the API to send to client
                }
            else: # Should ideally not happen
                return {"reply": "진료확인서 PDF 생성 중 예상치 못한 오류가 발생했습니다."}

        else:
            return {"reply": f"알 수 없는 증명서 종류입니다: '{certificate_type}'. '처방전' 또는 '진료확인서' 중에서 선택해주세요."}

    except MissingKoreanFontError:
        # This error is specifically from the PDF generation utility.
        print("MissingKoreanFontError caught in handle_certificate_request")
        return {"reply": "증명서 PDF 생성에 필요한 한글 글꼴을 찾을 수 없습니다. 시스템 관리자에게 문의해주세요.", "status_code": 500}
    except Exception as e:
        # Catch any other unexpected errors during the process.
        print(f"Error in handle_certificate_request for {name} ({rrn}), type {certificate_type}: {e}")
        return {"error": "증명서 발급 처리 중 예기치 않은 오류가 발생했습니다.", "status_code": 500}

def generate_chatbot_response(user_question: str, base64_image_data: str | None = None) -> dict:
    _func_args = locals()
    _module_path = sys.modules[__name__].__name__ if __name__ in sys.modules else __file__
    print(f"ENTERING: {_module_path}.generate_chatbot_response(args={{_func_args}})")
    """
    Generates a chatbot response using Google Gemini API.

    Args:
        user_question: The user's question.
        base64_image_data: Optional base64 encoded image data.

    Returns:
        A dictionary containing the bot's reply or an error message.
        e.g., {"reply": "bot_response_text"} or
              {"error": "error_message", "details": "...", "status_code": http_status_code}
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return {"error": "API key not configured.", "details": "GEMINI_API_KEY is not set.", "status_code": 500}

    try:
        genai.configure(api_key=api_key)
    except Exception as e:
        return {"error": "Failed to configure Generative AI.", "details": str(e), "status_code": 500}

    # Model initialization (e.g., "gemini-1.5-flash-latest")
    # Consider making model name a parameter or a constant if it changes frequently
    try:
        model = genai.GenerativeModel("gemini-1.5-flash-latest")
    except Exception as e:
        return {"error": "Failed to initialize Generative Model.", "details": str(e), "status_code": 500}

    prompt_parts = [SYSTEM_INSTRUCTION_PROMPT]

    if base64_image_data:
        try:
            # Remove potential "data:image/...;base64," prefix if present
            if "," in base64_image_data:
                header, encoded_data = base64_image_data.split(",", 1)
                mime_type = header.split(":")[1].split(";")[0] if ":" in header and ";" in header else "image/png" # default
            else:
                encoded_data = base64_image_data
                mime_type = "image/png" # default if no header

            image_bytes = base64.b64decode(encoded_data)

            image_blob = {
                "mime_type": mime_type,
                "data": image_bytes
            }
            prompt_parts.append(image_blob)
        except (base64.binascii.Error, ValueError) as e:
            return {"error": "Invalid base64 image data.", "details": str(e), "status_code": 400}
        except Exception as e: # Catch any other image processing errors
            return {"error": "Error processing image.", "details": str(e), "status_code": 500}

    prompt_parts.append(user_question)

    try:
        response = model.generate_content(prompt_parts)
    except Exception as e:
        # This can catch various API call related errors (network, quota, etc.)
        return {"error": "Failed to generate content from model.", "details": str(e), "status_code": 500}

    # Process the response (checking for blocks, safety ratings, etc.)
    try:
        if not response.candidates:
            if response.prompt_feedback.block_reason:
                return {
                    "error": "질문이 안전 기준에 의해 차단되었습니다.",
                    "details": f"차단 이유: {response.prompt_feedback.block_reason.name}",
                    "status_code": 400
                }
            else:
                return {"error": "챗봇으로부터 응답을 받지 못했습니다.", "details": "No candidates in response.", "status_code": 500}

        candidate = response.candidates[0]
        if not candidate.content.parts or not candidate.content.parts[0].text:
             # Check safety ratings if content is empty
            if candidate.finish_reason.name == "SAFETY":
                 # Try to get more specific safety information if available
                safety_detail = "안전상의 이유로 답변을 드릴 수 없습니다."
                for rating in candidate.safety_ratings:
                    if rating.blocked: # HARM_CATEGORY_DANGEROUS_CONTENT, etc.
                        safety_detail += f" (카테고리: {rating.category.name})"
                return {"error": safety_detail, "details": "Content blocked due to safety ratings.", "status_code": 400}
            return {"error": "챗봇으로부터 비어있는 응답을 받았습니다.", "details": "Empty content in response.", "status_code": 500}

        bot_response_text = candidate.content.parts[0].text
        # Store original raw text for logging, then clean it for parsing
        original_gemini_text = bot_response_text

        cleaned_text = bot_response_text.strip()
        if cleaned_text.startswith("```json"):
            cleaned_text = cleaned_text[len("```json"):].strip()
        elif cleaned_text.startswith("```"): # Handle if just ``` is present
            cleaned_text = cleaned_text[len("```"):].strip()

        if cleaned_text.endswith("```"):
            cleaned_text = cleaned_text[:-len("```")].strip()

        # Update bot_response_text to the cleaned version for parsing
        bot_response_text = cleaned_text

        print(f"Original Gemini raw text: >>>{original_gemini_text}<<<")
        print(f"Cleaned text for JSON parsing: >>>{bot_response_text}<<<")
        # Parse the JSON response from Gemini
        try:
            parsed_response = json.loads(bot_response_text)
        except json.JSONDecodeError as e:
            # The raw response is already printed in the previous step.
            # Here, we add some of it to the error details for context in the response.
            error_detail = f"JSONDecodeError: {str(e)}. Problematic text snippet (approx first 200 chars): '{bot_response_text[:200]}...'"
            # It's good to also log the full text server-side if not already done by the print earlier,
            # but the print statement added in Step 1 should cover server-side logging of the full text.
            print(f"JSON PARSING FAILED. Full raw text was logged above. Error: {str(e)}") # Re-iterate for clarity in logs
            return {
                "error": "AI로부터 유효하지 않은 JSON 형식의 응답을 받았습니다. 시스템 관리자에게 문의하거나 다시 시도해주세요.", # More user-friendly main error
                "details": error_detail, # For debugging
                "status_code": 500
            }

        intent = parsed_response.get("intent")
        parameters = parsed_response.get("parameters", {})
        user_query_from_response = parsed_response.get("user_query", user_question) # Fallback to original if not in response

        if intent == "general":
            reply = parsed_response.get("reply")
            if reply:
                return {"reply": reply}
            else:
                return {"error": "AI 응답에서 'reply' 필드를 찾을 수 없습니다 (intent=general).", "status_code": 500}
        elif intent == "reception":
            return handle_reception_request(parameters, user_query_from_response)
        elif intent == "payment":
            return handle_payment_request(parameters, user_query_from_response)
        elif intent == "certificate":
            return handle_certificate_request(parameters, user_query_from_response)
        else:
            return {"error": f"알 수 없거나 누락된 의도(intent) 값: {intent}", "status_code": 500}

    except Exception as e: # Catch errors during response processing
        # Log the exception for more detailed debugging if possible
        print(f"Error during response processing: {e}")
        return {"error": "챗봇 응답 처리 중 오류가 발생했습니다.", "details": str(e), "status_code": 500}
