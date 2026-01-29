from openai import OpenAI

SYSTEM_PROMPT = """
You are the official AI assistant for Dragon Coders, a software company.
Answer questions professionally about products, services, software development solutions, pricing, and documentation.
Guide users to official resources and provide helpful suggestions.
"""


class ChatBotBackend:
    def __init__(
        self,
        api_key,
        base_url="https://openrouter.ai/api/v1",
        model="openai/gpt-oss-20b:free",
    ):
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.histories = {}  # key = user_id, value = messages list

    def send_message(self, user_id, user_message):
        # Initialize history per user
        if user_id not in self.histories:
            self.histories[user_id] = [{"role": "system", "content": SYSTEM_PROMPT}]

        # Append user message
        self.histories[user_id].append({"role": "user", "content": user_message})

        # Call OpenAI / OpenRouter API
        response = self.client.chat.completions.create(
            model=self.model, messages=self.histories[user_id]
        )

        # Get assistant reply
        bot_reply = response.choices[0].message.content

        # Append bot reply to history
        self.histories[user_id].append({"role": "assistant", "content": bot_reply})

        return bot_reply
