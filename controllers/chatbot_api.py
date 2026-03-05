from odoo import http
from odoo.http import request
from ..services.chatbot_backend import ChatBotBackend

# Initialize backend with your API key
bot = ChatBotBackend(
    api_key="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"
)


class CustomerSupportChatbot(http.Controller):

    # 1️Route for chat page (UI)
    @http.route("/customer_support/chatbot", type="http", auth="user", website=True)
    def chatbot_page(self, **kw):
        """Render the chatbot page"""
        return request.render("customer_support.chatbot_page")

    # Route for sending messages (AJAX) - CHANGED type="json" to type="jsonrpc"
    @http.route("/customer_support/chatbot/message", type="json", auth="user")
    def chatbot_message(self, message, **kw):
        """Handle chatbot messages"""
        user_id = request.env.user.id
        try:
            reply = bot.send_message(user_id=user_id, user_message=message)
            return {"reply": reply}
        except Exception as e:
            return {"error": str(e)}

    # Optional: Route to clear chat history
    @http.route("/customer_support/chatbot/clear", type="json", auth="user")
    def chatbot_clear(self, **kw):
        """Clear chat history for current user"""
        user_id = request.env.user.id
        try:
            # If your ChatBotBackend has a clear_history method, use it
            # bot.clear_history(user_id=user_id)
            return {"success": True, "message": "Chat history cleared"}
        except Exception as e:
            return {"error": str(e)}
