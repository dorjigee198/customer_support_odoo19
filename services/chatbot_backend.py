from openai import OpenAI
import json

SYSTEM_PROMPT = """
You are Dragon Coders AI assistant. Answer questions about our software services briefly and professionally.
"""

MAX_HISTORY = 6


class ChatBotBackend:
    def __init__(
        self,
        api_key,
        base_url="https://openrouter.ai/api/v1",
        model="openai/gpt-oss-20b:free",
    ):
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.histories = {}

    def send_message(self, user_id, user_message):
        # Initialize history per user
        if user_id not in self.histories:
            self.histories[user_id] = [{"role": "system", "content": SYSTEM_PROMPT}]

        # Append user message
        self.histories[user_id].append({"role": "user", "content": user_message})

        # Trim history - keep system prompt + last 6 messages only
        if len(self.histories[user_id]) > MAX_HISTORY:
            self.histories[user_id] = [self.histories[user_id][0]] + self.histories[
                user_id
            ][-MAX_HISTORY:]

        # Call OpenRouter API
        try:
            response = self.client.chat.completions.create(
                model=self.model, messages=self.histories[user_id]
            )

            # Handle both object and string responses
            if isinstance(response, str):
                response = json.loads(response)
                bot_reply = response["choices"][0]["message"]["content"]
            else:
                bot_reply = response.choices[0].message.content

        except Exception as e:
            return "Sorry, I am currently unavailable. Please try again later."

        # Append bot reply to history
        self.histories[user_id].append({"role": "assistant", "content": bot_reply})

        return bot_reply
