import sys # Added for logging
from flask import Blueprint, request, jsonify, render_template
# Removed: os, google.generativeai, base64, io since they are handled by the service

from app.services.chatbot_service import generate_chatbot_response

chatbot_bp = Blueprint('chatbot', __name__, url_prefix='/api')

# SYSTEM_INSTRUCTION_PROMPT is now defined in chatbot_service.py

@chatbot_bp.route('/chatbot', methods=['POST'])
def handle_chatbot_request():
    _func_args = locals()
    _module_path = sys.modules[__name__].__name__ if __name__ in sys.modules else __file__
    print(f"ENTERING: {_module_path}.handle_chatbot_request(args={{_func_args}})")
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON request"}), 400

    user_question = data.get('message')
    base64_image_data = data.get('base64_image_data') # Optional

    if not user_question:
        return jsonify({"error": "No message (user_question) provided"}), 400

    # Call the service function
    service_response = generate_chatbot_response(user_question, base64_image_data)

    if "error" in service_response:
        # The service returns a 'status_code' key for errors, use it.
        # Also, the service might put the user-facing message in 'error' or 'details'
        # For simplicity, returning the whole error dict from service (excluding status_code for jsonify)
        status_code = service_response.pop("status_code", 500)
        # Some error messages from the service are already user-friendly for 'reply'
        # If the service has a specific "reply" field for errors, use that.
        # The current service returns "error" for the main error message and "details" for more info.
        # The original route often had a "reply" field even for errors.
        # Let's ensure the JSON response to client has an "error" field for client-side logic if needed,
        # and "reply" for user display.

        error_payload = {"error": service_response.get("error", "An unknown error occurred.")}
        if "details" in service_response:
            error_payload["details"] = service_response["details"]

        # For user display, use the 'error' message from service as 'reply'
        error_payload["reply"] = service_response.get("error", "죄송합니다. 현재 답변을 생성할 수 없습니다.")

        return jsonify(error_payload), status_code
    else:
        # Successful response from service, which might include 'reply',
        # 'pdf_filename', 'pdf_data_base64', etc.
        return jsonify(service_response)

# The chatbot_interface route remains unchanged.
# Example of how to register this blueprint in app/__init__.py:
# from .routes.chatbot import chatbot_bp
# app.register_blueprint(chatbot_bp)

@chatbot_bp.route('/interface')
def chatbot_interface():
    """Renders the chatbot interface page."""
    _func_args = locals()
    _module_path = sys.modules[__name__].__name__ if __name__ in sys.modules else __file__
    print(f"ENTERING: {_module_path}.chatbot_interface(args={{_func_args}})")
    return render_template("chatbot_interface.html")
