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
