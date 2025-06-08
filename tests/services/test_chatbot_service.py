import unittest
from unittest.mock import patch, MagicMock, ANY
import os
import base64
import sys

# Ensure the app package is importable during test collection
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.services.chatbot_service import generate_chatbot_response, SYSTEM_INSTRUCTION_PROMPT

class TestChatbotService(unittest.TestCase):

    def setUp(self):
        self.user_question = "오늘 날씨 어때요?"
        self.api_key = "test_api_key"
        self.mock_model_response_text = "저는 날씨 정보는 드릴 수 없어요. 저는 늘봄이입니다."

    @patch('app.services.chatbot_service.os.getenv')
    @patch('app.services.chatbot_service.genai.configure')
    @patch('app.services.chatbot_service.genai.GenerativeModel')
    def test_generate_chatbot_response_success(self, mock_generative_model, mock_genai_configure, mock_os_getenv):
        mock_os_getenv.return_value = self.api_key

        mock_model_instance = MagicMock()
        mock_response = MagicMock()
        mock_candidate = MagicMock()
        mock_content_part = MagicMock()
        mock_content_part.text = self.mock_model_response_text
        mock_candidate.content.parts = [mock_content_part]
        mock_candidate.finish_reason.name = "STOP" # Ensure finish_reason is not SAFETY
        mock_response.candidates = [mock_candidate]
        mock_response.prompt_feedback.block_reason = None # No block reason
        mock_model_instance.generate_content.return_value = mock_response
        mock_generative_model.return_value = mock_model_instance

        result = generate_chatbot_response(self.user_question)

        self.assertIn("reply", result)
        self.assertEqual(result["reply"], self.mock_model_response_text)
        mock_os_getenv.assert_called_once_with("GEMINI_API_KEY")
        mock_genai_configure.assert_called_once_with(api_key=self.api_key)
        mock_generative_model.assert_called_once_with("gemini-1.5-flash-latest")

        # Check prompt parts passed to generate_content
        expected_prompt_parts = [SYSTEM_INSTRUCTION_PROMPT, self.user_question]
        mock_model_instance.generate_content.assert_called_once_with(expected_prompt_parts)

    @patch('app.services.chatbot_service.os.getenv')
    @patch('app.services.chatbot_service.genai.configure')
    @patch('app.services.chatbot_service.genai.GenerativeModel')
    def test_generate_chatbot_response_with_image(self, mock_generative_model, mock_genai_configure, mock_os_getenv):
        mock_os_getenv.return_value = self.api_key
        mock_model_instance = MagicMock()
        # ... (setup model response as in previous test)
        mock_response = MagicMock()
        mock_candidate = MagicMock()
        mock_content_part = MagicMock()
        mock_content_part.text = "이미지를 잘 봤어요. 이것은..."
        mock_candidate.content.parts = [mock_content_part]
        mock_candidate.finish_reason.name = "STOP"
        mock_response.candidates = [mock_candidate]
        mock_response.prompt_feedback.block_reason = None
        mock_model_instance.generate_content.return_value = mock_response
        mock_generative_model.return_value = mock_model_instance

        raw_image_data = b"fake_image_bytes"
        base64_image_data_full = "data:image/png;base64," + base64.b64encode(raw_image_data).decode('utf-8')

        result = generate_chatbot_response(self.user_question, base64_image_data_full)

        self.assertIn("reply", result)
        # mock_model_instance.generate_content.assert_called_once()
        args, _ = mock_model_instance.generate_content.call_args
        prompt_parts_sent = args[0]

        self.assertEqual(len(prompt_parts_sent), 3) # System prompt, image, user question
        self.assertEqual(prompt_parts_sent[0], SYSTEM_INSTRUCTION_PROMPT)
        self.assertIsInstance(prompt_parts_sent[1], dict) # Image blob
        self.assertEqual(prompt_parts_sent[1]["mime_type"], "image/png")
        self.assertEqual(prompt_parts_sent[1]["data"], raw_image_data)
        self.assertEqual(prompt_parts_sent[2], self.user_question)


    def test_generate_chatbot_response_no_api_key(self):
        with patch('app.services.chatbot_service.os.getenv', return_value=None):
            result = generate_chatbot_response(self.user_question)
            self.assertIn("error", result)
            self.assertEqual(result["error"], "API key not configured.")
            self.assertEqual(result["status_code"], 500)

    @patch('app.services.chatbot_service.os.getenv', return_value="test_key")
    @patch('app.services.chatbot_service.genai.configure', side_effect=Exception("Config error"))
    def test_generate_chatbot_response_genai_config_error(self, mock_genai_configure, mock_os_getenv):
        result = generate_chatbot_response(self.user_question)
        self.assertIn("error", result)
        self.assertEqual(result["error"], "Failed to configure Generative AI.")
        self.assertEqual(result["details"], "Config error")
        self.assertEqual(result["status_code"], 500)

    @patch('app.services.chatbot_service.os.getenv', return_value="test_key")
    @patch('app.services.chatbot_service.genai.configure')
    @patch('app.services.chatbot_service.genai.GenerativeModel', side_effect=Exception("Model init error"))
    def test_generate_chatbot_response_model_init_error(self, mock_gm_init, mock_configure, mock_getenv):
        result = generate_chatbot_response(self.user_question)
        self.assertIn("error", result)
        self.assertEqual(result["error"], "Failed to initialize Generative Model.")
        self.assertEqual(result["details"], "Model init error")
        self.assertEqual(result["status_code"], 500)


    @patch('app.services.chatbot_service.os.getenv', return_value="test_key")
    @patch('app.services.chatbot_service.genai.configure')
    @patch('app.services.chatbot_service.genai.GenerativeModel')
    def test_generate_chatbot_response_generation_error(self, mock_generative_model, mock_genai_configure, mock_os_getenv):
        mock_model_instance = MagicMock()
        mock_model_instance.generate_content.side_effect = Exception("API call failed")
        mock_generative_model.return_value = mock_model_instance

        result = generate_chatbot_response(self.user_question)
        self.assertIn("error", result)
        self.assertEqual(result["error"], "Failed to generate content from model.")
        self.assertEqual(result["details"], "API call failed")
        self.assertEqual(result["status_code"], 500)

    @patch('app.services.chatbot_service.os.getenv', return_value="test_key")
    @patch('app.services.chatbot_service.genai.configure')
    @patch('app.services.chatbot_service.genai.GenerativeModel')
    def test_generate_chatbot_response_prompt_blocked(self, mock_generative_model, mock_genai_configure, mock_os_getenv):
        mock_model_instance = MagicMock()
        mock_response = MagicMock()
        mock_response.candidates = [] # No candidates
        mock_response.prompt_feedback.block_reason = "SAFETY" # Using string for simplicity, actual is enum-like
        mock_response.prompt_feedback.block_reason.name = "SAFETY_BLOCK_REASON" # Mocking the .name attribute
        mock_model_instance.generate_content.return_value = mock_response
        mock_generative_model.return_value = mock_model_instance

        result = generate_chatbot_response(self.user_question)
        self.assertIn("error", result)
        self.assertEqual(result["error"], "질문이 안전 기준에 의해 차단되었습니다.")
        self.assertEqual(result["details"], "차단 이유: SAFETY_BLOCK_REASON")
        self.assertEqual(result["status_code"], 400)

    @patch('app.services.chatbot_service.os.getenv', return_value="test_key")
    @patch('app.services.chatbot_service.genai.configure')
    @patch('app.services.chatbot_service.genai.GenerativeModel')
    def test_generate_chatbot_response_content_safety_blocked(self, mock_gm, mock_config, mock_getenv):
        mock_model_instance = MagicMock()
        mock_response = MagicMock()
        mock_candidate = MagicMock()
        mock_candidate.content.parts = [] # Empty parts
        mock_candidate.finish_reason.name = "SAFETY"

        # Mock safety ratings
        rating_mock = MagicMock()
        rating_mock.blocked = True
        rating_mock.category.name = "HARM_CATEGORY_DANGEROUS_CONTENT"
        mock_candidate.safety_ratings = [rating_mock]

        mock_response.candidates = [mock_candidate]
        mock_model_instance.generate_content.return_value = mock_response
        mock_gm.return_value = mock_model_instance

        result = generate_chatbot_response(self.user_question)
        self.assertIn("error", result)
        self.assertTrue("안전상의 이유로 답변을 드릴 수 없습니다." in result["error"])
        self.assertTrue("(카테고리: HARM_CATEGORY_DANGEROUS_CONTENT)" in result["error"])
        self.assertEqual(result["status_code"], 400)


    @patch('app.services.chatbot_service.os.getenv', return_value="test_key")
    @patch('app.services.chatbot_service.genai.configure')
    @patch('app.services.chatbot_service.genai.GenerativeModel')
    def test_generate_chatbot_response_empty_response_text(self, mock_gm, mock_config, mock_getenv):
        mock_model_instance = MagicMock()
        mock_response = MagicMock()
        mock_candidate = MagicMock()
        mock_content_part = MagicMock()
        mock_content_part.text = "" # Empty text
        mock_candidate.content.parts = [mock_content_part]
        mock_candidate.finish_reason.name = "STOP"
        mock_response.candidates = [mock_candidate]
        mock_response.prompt_feedback.block_reason = None
        mock_model_instance.generate_content.return_value = mock_response
        mock_gm.return_value = mock_model_instance

        result = generate_chatbot_response(self.user_question)
        self.assertIn("error", result) # Should be an error as per service logic for empty text
        self.assertEqual(result["error"], "챗봇으로부터 비어있는 응답을 받았습니다.")
        self.assertEqual(result["status_code"], 500)


    def test_generate_chatbot_response_invalid_base64_image(self):
        with patch('app.services.chatbot_service.os.getenv', return_value=self.api_key), \
             patch('app.services.chatbot_service.genai.configure'), \
             patch('app.services.chatbot_service.genai.GenerativeModel'): # Mock genai setup

            invalid_base64 = "data:image/png;base64,not_really_base64"
            result = generate_chatbot_response(self.user_question, invalid_base64)
            self.assertIn("error", result)
            self.assertEqual(result["error"], "Invalid base64 image data.")
            self.assertEqual(result["status_code"], 400)

if __name__ == '__main__':
    unittest.main()

# Import handler functions to be patched/tested if not already at top level
from app.services.chatbot_service import (
    handle_reception_request,
    handle_payment_request,
    handle_certificate_request
)
# Import specific services that handler functions might call, for mocking them
# For example, if handle_reception_request calls functions from reception_service
from app.services import reception_service, payment_service, certificate_service
from app.utils import pdf_generator # For MissingKoreanFontError

# Standard library imports
import json # For creating mock JSON responses from Gemini

class TestChatbotServiceHandlers(unittest.TestCase):
    def setUp(self):
        self.user_question = "A user's question"
        self.api_key = "test_api_key_for_handlers"
        # Common patchers for most tests in this class
        self.getenv_patcher = patch('app.services.chatbot_service.os.getenv', return_value=self.api_key)
        self.configure_patcher = patch('app.services.chatbot_service.genai.configure')
        self.model_patcher = patch('app.services.chatbot_service.genai.GenerativeModel')

        self.mock_os_getenv = self.getenv_patcher.start()
        self.mock_genai_configure = self.configure_patcher.start()
        self.mock_generative_model = self.model_patcher.start()

        # Mock the model instance and its generate_content method by default
        self.mock_model_instance = MagicMock()
        self.mock_generative_model.return_value = self.mock_model_instance


    def tearDown(self):
        self.getenv_patcher.stop()
        self.configure_patcher.stop()
        self.model_patcher.stop()

    def _prepare_mock_gemini_response(self, response_dict):
        """Helper to set up the mock model's response."""
        mock_response = MagicMock()
        mock_candidate = MagicMock()
        mock_content_part = MagicMock()
        mock_content_part.text = json.dumps(response_dict) # Gemini returns a JSON string
        mock_candidate.content.parts = [mock_content_part]
        mock_candidate.finish_reason.name = "STOP"
        mock_response.candidates = [mock_candidate]
        mock_response.prompt_feedback.block_reason = None
        self.mock_model_instance.generate_content.return_value = mock_response

    @patch('app.services.chatbot_service.handle_reception_request')
    def test_generate_chatbot_response_routes_to_reception(self, mock_handle_reception):
        mock_handle_reception.return_value = {"reply": "Reception handled"}
        gemini_response_data = {
            "intent": "reception",
            "parameters": {"name": "테스트"},
            "user_query": self.user_question
        }
        self._prepare_mock_gemini_response(gemini_response_data)

        result = generate_chatbot_response(self.user_question)

        self.assertEqual(result, {"reply": "Reception handled"})
        mock_handle_reception.assert_called_once_with(gemini_response_data["parameters"], gemini_response_data["user_query"])

    @patch('app.services.chatbot_service.handle_payment_request')
    def test_generate_chatbot_response_routes_to_payment(self, mock_handle_payment):
        mock_handle_payment.return_value = {"reply": "Payment handled"}
        gemini_response_data = {
            "intent": "payment",
            "parameters": {"amount": "1000"},
            "user_query": self.user_question
        }
        self._prepare_mock_gemini_response(gemini_response_data)

        result = generate_chatbot_response(self.user_question)

        self.assertEqual(result, {"reply": "Payment handled"})
        mock_handle_payment.assert_called_once_with(gemini_response_data["parameters"], gemini_response_data["user_query"])

    @patch('app.services.chatbot_service.handle_certificate_request')
    def test_generate_chatbot_response_routes_to_certificate(self, mock_handle_certificate):
        mock_handle_certificate.return_value = {"reply": "Certificate handled"}
        gemini_response_data = {
            "intent": "certificate",
            "parameters": {"type": "prescription"},
            "user_query": self.user_question
        }
        self._prepare_mock_gemini_response(gemini_response_data)

        result = generate_chatbot_response(self.user_question)

        self.assertEqual(result, {"reply": "Certificate handled"})
        mock_handle_certificate.assert_called_once_with(gemini_response_data["parameters"], gemini_response_data["user_query"])

    def test_generate_chatbot_response_handles_general_intent(self):
        gemini_response_data = {
            "intent": "general",
            "reply": "This is a general answer."
        }
        self._prepare_mock_gemini_response(gemini_response_data)

        result = generate_chatbot_response(self.user_question)
        self.assertEqual(result, {"reply": "This is a general answer."})

    def test_generate_chatbot_response_handles_json_decode_error(self):
        # Prepare malformed JSON
        mock_response = MagicMock()
        mock_candidate = MagicMock()
        mock_content_part = MagicMock()
        mock_content_part.text = "This is not valid JSON {{"
        mock_candidate.content.parts = [mock_content_part]
        mock_candidate.finish_reason.name = "STOP"
        mock_response.candidates = [mock_candidate]
        mock_response.prompt_feedback.block_reason = None
        self.mock_model_instance.generate_content.return_value = mock_response

        result = generate_chatbot_response(self.user_question)
        self.assertIn("error", result)
        self.assertEqual(result["error"], "AI로부터 유효하지 않은 JSON 응답을 받았습니다.")
        self.assertEqual(result["status_code"], 500)

    def test_generate_chatbot_response_handles_missing_reply_for_general_intent(self):
        gemini_response_data = {"intent": "general"} # Missing "reply"
        self._prepare_mock_gemini_response(gemini_response_data)

        result = generate_chatbot_response(self.user_question)
        self.assertIn("error", result)
        self.assertEqual(result["error"], "AI 응답에서 'reply' 필드를 찾을 수 없습니다 (intent=general).")
        self.assertEqual(result["status_code"], 500)

    def test_generate_chatbot_response_handles_unknown_intent(self):
        gemini_response_data = {
            "intent": "unknown_intent",
            "parameters": {},
            "user_query": self.user_question
        }
        self._prepare_mock_gemini_response(gemini_response_data)

        result = generate_chatbot_response(self.user_question)
        self.assertIn("error", result)
        self.assertEqual(result["error"], "알 수 없거나 누락된 의도(intent) 값: unknown_intent")
        self.assertEqual(result["status_code"], 500)

    # --- Tests for handle_reception_request ---
    @patch('app.services.chatbot_service.reception_service.lookup_reservation')
    def test_handle_reception_patient_not_found(self, mock_lookup_reservation):
        test_name = "신규고객"
        test_rrn = "000000-0000000"
        mock_lookup_reservation.return_value = None # Patient not found

        params = {"name": test_name, "rrn": test_rrn, "symptom": "fever"} # Symptom might or might not be provided

        # Directly test the handler function
        result = handle_reception_request(params, "some query for not found patient")

        expected_reply = f"죄송합니다, {test_name}님의 정보를 시스템에서 찾을 수 없습니다. 데스크에 문의하여 등록을 먼저 진행해주시기 바랍니다."
        self.assertEqual(result, {"reply": expected_reply})
        mock_lookup_reservation.assert_called_once_with(test_name, test_rrn)

    @patch('app.services.chatbot_service.reception_service.lookup_reservation')
    def test_handle_reception_existing_patient_registered(self, mock_lookup_reservation):
        mock_lookup_reservation.return_value = {
            "name": "김철수", "rrn": "654321-7654321", "status": "Registered",
            "department": "외과", "ticket_number": "S002"
        }
        params = {"name": "김철수", "rrn": "654321-7654321"}
        result = handle_reception_request(params, "some query")
        self.assertEqual(result, {"reply": "김철수님은 이미 외과으로 접수되셨습니다. 대기번호는 S002번 입니다. 추가 문의가 있으신가요?"})

    def test_handle_reception_missing_name_rrn(self):
        params = {}
        result = handle_reception_request(params, "some query")
        self.assertEqual(result, {"reply": "접수를 위해 성함과 주민등록번호를 알려주시겠어요? 예: 홍길동, 123456-1234567"})

    @patch('app.services.chatbot_service.reception_service.lookup_reservation', return_value=None)
    def test_handle_reception_new_patient_no_symptom(self, mock_lookup):
        params = {"name": "박영희", "rrn": "001122-0011220"}
        # Patching SYMPTOMS directly in the chatbot_service's scope if it's imported there
        with patch('app.services.chatbot_service.SYMPTOMS', [("fever", "발열"), ("cough", "기침")]):
            result = handle_reception_request(params, "some query")
            self.assertEqual(result, {"reply": "어떤 증상으로 방문하셨나요? 다음 중에서 선택해주세요: 발열, 기침 (예: 발열, 기침 등)"})

    # --- Tests for handle_payment_request ---
    @patch('app.services.chatbot_service.payment_service.update_reservation_with_payment_details')
    @patch('app.services.chatbot_service.reception_service.lookup_reservation')
    def test_handle_payment_confirmation_success(self, mock_lookup, mock_update_payment):
        mock_lookup.return_value = {"name": "고길동", "rrn": "850515-1987654", "status": "Registered", "department": "내과"}
        mock_update_payment.return_value = True

        params = {
            "name": "고길동", "rrn": "850515-1987654",
            "payment_stage": "confirmation", "payment_method": "card",
            "total_fee": "35000", "prescription_names": ["감기약", "소화제"]
        }
        result = handle_payment_request(params, "some query")
        self.assertEqual(result, {"reply": "고길동님의 결제가 card로 완료되었습니다. 총 35000원이 결제되었습니다. 감사합니다."})
        mock_update_payment.assert_called_once_with("850515-1987654", ["감기약", "소화제"], 35000)

    @patch('app.services.chatbot_service.payment_service.load_department_prescriptions')
    @patch('app.services.chatbot_service.reception_service.lookup_reservation')
    def test_handle_payment_initial_success(self, mock_lookup, mock_load_prescriptions):
        mock_lookup.return_value = {"name": "고길동", "rrn": "850515-1987654", "status": "Registered", "department": "내과"}
        mock_load_prescriptions.return_value = {
            "prescriptions_for_display": [{"name": "감기약", "fee": 15000}, {"name": "소화제", "fee": 20000}],
            "total_fee": 35000,
            "prescription_names": ["감기약", "소화제"]
        }
        params = {"name": "고길동", "rrn": "850515-1987654", "payment_stage": "initial"}
        result = handle_payment_request(params, "some query")
        expected_reply = (
            "고길동님의 처방 내역입니다:\n- 감기약: 15000원\n- 소화제: 20000원\n"
            "총 금액은 35000원 입니다. "
            "결제하시겠습니까? 그렇다면 '현금' 또는 '카드'로 결제 수단을 말씀해주시고, 처방내역과 금액도 함께 확인해주세요. (예: 카드로 결제, 35000원, 처방내역: 감기약, 소화제)"
        )
        self.assertEqual(result, {"reply": expected_reply})

    # --- Tests for handle_certificate_request ---
    @patch('app.services.chatbot_service.base64.b64encode')
    @patch('app.services.chatbot_service.certificate_service.prepare_medical_confirmation_pdf')
    @patch('app.services.chatbot_service.reception_service.lookup_reservation')
    def test_handle_certificate_confirmation_success(self, mock_lookup, mock_prepare_pdf, mock_b64encode):
        mock_lookup.return_value = {"name": "박민지", "rrn": "950101-2000000", "status": "Paid", "department": "정형외과"}
        mock_prepare_pdf.return_value = (b"pdf_bytes_data", "confirmation_950101-2000000.pdf")
        mock_b64encode.return_value = b"base64_encoded_data"

        params = {"name": "박민지", "rrn": "950101-2000000", "certificate_type": "confirmation"}
        result = handle_certificate_request(params, "some query")

        expected_result = {
            "reply": "박민지님의 진료확인서 발급이 완료되었습니다. 파일명: confirmation_950101-2000000.pdf",
            "pdf_filename": "confirmation_950101-2000000.pdf",
            "pdf_data_base64": "base64_encoded_data"
        }
        self.assertEqual(result, expected_result)
        mock_b64encode.assert_called_once_with(b"pdf_bytes_data")
        mock_prepare_pdf.assert_called_once_with("박민지", "950101-2000000", "정형외과")

    @patch('app.services.chatbot_service.certificate_service.get_prescription_data_for_pdf')
    @patch('app.services.chatbot_service.reception_service.lookup_reservation')
    def test_handle_certificate_prescription_needs_payment(self, mock_lookup, mock_get_presc_data):
        mock_lookup.return_value = {"name": "이영수", "rrn": "750101-1000000", "status": "Registered", "department": "내과"}
        # Simulate get_prescription_data_for_pdf returning an error because payment is not done
        mock_get_presc_data.return_value = ("NEEDS_PAYMENT", "수납이 완료되지 않았습니다. 먼저 수납을 진행해주세요.")

        params = {"name": "이영수", "rrn": "750101-1000000", "certificate_type": "prescription"}
        result = handle_certificate_request(params, "some query")

        self.assertEqual(result, {"reply": "처방전을 발급할 수 없습니다: 수납이 완료되지 않았습니다. 먼저 수납을 진행해주세요."})

    @patch('app.services.chatbot_service.certificate_service.prepare_medical_confirmation_pdf')
    @patch('app.services.chatbot_service.reception_service.lookup_reservation')
    def test_handle_certificate_missing_font_error(self, mock_lookup, mock_prepare_pdf):
        mock_lookup.return_value = {"name": "최지우", "rrn": "880101-2000000", "status": "Paid", "department": "피부과"}
        mock_prepare_pdf.side_effect = pdf_generator.MissingKoreanFontError("Font not found")

        params = {"name": "최지우", "rrn": "880101-2000000", "certificate_type": "confirmation"}
        result = handle_certificate_request(params, "some query")

        self.assertEqual(result, {
            "reply": "증명서 PDF 생성에 필요한 한글 글꼴을 찾을 수 없습니다. 시스템 관리자에게 문의해주세요.",
            "status_code": 500
        })

    # --- Tests for handle_reception_request: Pending Status ---
    @patch('app.services.chatbot_service.update_reservation_status')
    @patch('app.services.chatbot_service.new_ticket')
    @patch('app.services.chatbot_service.lookup_reservation')
    def test_handle_reception_pending_patient_check_in_success_with_dept(self, mock_lookup_reservation, mock_new_ticket, mock_update_status):
        mock_patient_name = "보류환자"
        mock_patient_rrn = "PEND01-PENDING"
        mock_pending_dept = "가정의학과"
        mock_new_ticket_num = "P007"

        mock_lookup_reservation.return_value = {
            "name": mock_patient_name, "rrn": mock_patient_rrn,
            "status": "Pending", "department": mock_pending_dept
        }
        mock_new_ticket.return_value = mock_new_ticket_num
        mock_update_status.return_value = True

        params = {"name": mock_patient_name, "rrn": mock_patient_rrn} # User might not provide symptom if dept exists
        result = handle_reception_request(params, "Check me in.")

        expected_reply = f"{mock_patient_name}님의 예약이 확인되었습니다. {mock_pending_dept}으로 접수되었으며, 대기번호는 {mock_new_ticket_num}번입니다."
        self.assertEqual(result, {"reply": expected_reply})
        mock_lookup_reservation.assert_called_once_with(mock_patient_name, mock_patient_rrn)
        mock_new_ticket.assert_called_once_with(mock_pending_dept)
        mock_update_status.assert_called_once_with(
            mock_patient_rrn, 'Registered',
            department=mock_pending_dept,
            ticket_number=mock_new_ticket_num,
            name=mock_patient_name
        )

    @patch('app.services.chatbot_service.lookup_reservation')
    def test_handle_reception_pending_patient_no_dept_asks_symptom(self, mock_lookup_reservation):
        mock_patient_name = "보류환자투"
        mock_patient_rrn = "PEND02-PENDING"
        mock_lookup_reservation.return_value = {
            "name": mock_patient_name, "rrn": mock_patient_rrn,
            "status": "Pending", "department": None # No department
        }

        # Patch SYMPTOMS in the context of where handle_reception_request will see it
        with patch('app.services.chatbot_service.SYMPTOMS', [("fever", "발열"), ("cough", "기침")]):
            params = {"name": mock_patient_name, "rrn": mock_patient_rrn} # No symptom provided by user yet
            result = handle_reception_request(params, "Check me in, no symptom mentioned.")

            expected_reply = f"{mock_patient_name}님의 예약은 확인되었으나, 진료 부서가 지정되지 않았습니다. 어떤 증상으로 방문하셨나요? 예: 발열, 기침"
            self.assertEqual(result, {"reply": expected_reply})
        mock_lookup_reservation.assert_called_once_with(mock_patient_name, mock_patient_rrn)

    @patch('app.services.chatbot_service.update_reservation_status')
    @patch('app.services.chatbot_service.new_ticket')
    @patch('app.services.chatbot_service.handle_choose_symptom_action')
    @patch('app.services.chatbot_service.lookup_reservation')
    def test_handle_reception_pending_patient_no_dept_with_symptom_success(
        self, mock_lookup_reservation, mock_handle_choose_symptom, mock_new_ticket, mock_update_status
    ):
        mock_patient_name = "보류환자쓰리"
        mock_patient_rrn = "PEND03-PENDING"
        user_provided_symptom = "cough" # This is the key
        derived_department = "호흡기내과"
        mock_new_ticket_num = "P008"

        mock_lookup_reservation.return_value = {
            "name": mock_patient_name, "rrn": mock_patient_rrn,
            "status": "Pending", "department": None
        }
        # Mocking SYM_TO_DEPT and SYMPTOMS is implicitly handled if handle_choose_symptom_action is correctly mocked
        # and if the symptom key provided is valid.
        mock_handle_choose_symptom.return_value = {"department": derived_department, "ticket": "ignored_ticket_from_choose_symptom"}
        mock_new_ticket.return_value = mock_new_ticket_num
        mock_update_status.return_value = True

        # User provides symptom in this turn because bot asked in a hypothetical previous turn, or user is proactive
        params = {"name": mock_patient_name, "rrn": mock_patient_rrn, "symptom": user_provided_symptom}
        result = handle_reception_request(params, f"I have a {user_provided_symptom}.")

        expected_reply = f"{mock_patient_name}님의 예약이 확인되었습니다. {derived_department}으로 접수되었으며, 대기번호는 {mock_new_ticket_num}번입니다."
        self.assertEqual(result, {"reply": expected_reply})

        mock_lookup_reservation.assert_called_once_with(mock_patient_name, mock_patient_rrn)
        mock_handle_choose_symptom.assert_called_once_with(user_provided_symptom)
        mock_new_ticket.assert_called_once_with(derived_department)
        mock_update_status.assert_called_once_with(
            mock_patient_rrn, 'Registered',
            department=derived_department,
            ticket_number=mock_new_ticket_num,
            name=mock_patient_name
        )
