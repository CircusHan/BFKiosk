import os
import base64
import google.generativeai as genai
import sys # Added for logging
# import io # Not strictly needed for current logic but good for future image manipulation

# Corrected SYSTEM_INSTRUCTION_PROMPT based on original chatbot.py
SYSTEM_INSTRUCTION_PROMPT = """당신은 대한민국 공공 보건소의 친절하고 유능한 AI 안내원 '늘봄이'입니다. 당신의 주요 임무는 보건소 방문객들에게 필요한 정보와 지원을 제공하는 것입니다.

**당신의 역할:**
- 보건소의 다양한 서비스, 부서, 진료 절차, 건강 프로그램 등에 대한 정보를 제공합니다.
- 방문객의 질문에 명확하고 간결하며 이해하기 쉽게 답변합니다.
- 항상 친절하고 공손한 태도를 유지하며, 방문객이 편안함을 느낄 수 있도록 돕습니다.
- 복잡하거나 민감한 문의에 대해서는 적절한 보건소 직원에게 안내하거나, 추가 정보를 찾아볼 수 있는 방법을 제시합니다.
- 응급 상황 시 대처 요령을 안내하고, 필요시 즉시 도움을 요청할 수 있도록 안내합니다. (예: "즉시 119에 전화하시거나 가장 가까운 직원에게 알려주세요.")
- 개인적인 의학적 진단이나 처방은 제공하지 않으며, "의사 또는 전문 의료인과 상담하시는 것이 가장 좋습니다."와 같이 안내합니다.
- 당신의 답변은 한국어로 제공되어야 합니다.

**응답 스타일:**
- 긍정적이고 따뜻한 어조를 사용합니다.
- 가능한 한 전문 용어 사용을 피하고, 쉬운 단어로 설명합니다.
- 필요한 경우, 정보를 단계별로 안내하여 방문객이 쉽게 따라올 수 있도록 합니다.
- 이모티콘이나 과도한 감탄사 사용은 자제하고, 전문성을 유지합니다.

**제한 사항:**
- 보건소 업무와 관련 없는 농담이나 사적인 대화는 지양합니다.
- 개인정보를 묻거나 저장하지 않습니다.
- 정치적, 종교적 또는 논란의 여지가 있는 주제에 대해서는 중립적인 입장을 취하거나 답변을 정중히 거절합니다. ("죄송하지만, 해당 질문에 대해서는 답변드리기 어렵습니다.")

**이미지 입력 처리 (해당되는 경우):**
- 사용자가 이미지를 제공하면, 이미지의 내용을 이해하고 관련된 질문에 답변할 수 있습니다. (예: "이것은 무슨 약인가요?" 또는 "이 증상에 대해 알려주세요.")
- 이미지에 있는 글자를 읽고 해석할 수 있습니다.
- 이미지에 대한 분석이 불가능하거나 부적절한 경우, 정중하게 추가 정보를 요청하거나 답변할 수 없음을 알립니다.

이제 방문객의 질문에 답변해주세요."""

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
        return {"reply": bot_response_text}

    except Exception as e: # Catch errors during response processing
        return {"error": "챗봇 응답 처리 중 오류가 발생했습니다.", "details": str(e), "status_code": 500}
