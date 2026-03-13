import requests
import json
import logging
import time

_logger = logging.getLogger(__name__)

# ── Configuration ────────────────────────────────────────────────────────────
OLLAMA_BASE_URL = "http://192.168.0.240:11434"
MODEL = "qwen2.5:7b"  # Your fastest currently installed model


# ── SUPPORT BOT (Dragon Coders specific with RAG) ────────────────────────────
SYSTEM_PROMPT = """
You are the official AI support assistant for Dragon Coders.

STRICT RULES:
1. Answer ONLY using the provided CONTEXT.
2. NEVER guess or invent information.
3. Only discuss Dragon Coders company, services, projects.
4. For bugs/errors/technical issues → classify as "technical".
5. Be concise, professional, friendly.

RESPONSE FORMAT — JSON only:
- General: {"intent": "general", "reply": "..."}
- Technical: {"intent": "technical", "summary": "One-sentence issue summary"}
- Off-topic: {"intent": "offtopic", "reply": "I can only help with Dragon Coders questions."}
- No info: {"intent": "no_context", "reply": "I don't have that information. Contact support@dragoncoders.com or create a New Ticket to reach the Support Team"}

Return ONLY valid JSON. No extra text.
"""

MAX_HISTORY = 4
MAX_TOKENS = 250


class ChatBotBackend:
    def __init__(self, base_url=OLLAMA_BASE_URL, model=MODEL):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.histories = {}
        self._query_cache = {}  # user_id → {query_hash: (intent, reply)}

    def send_message(self, user_id, user_message, odoo_env=None):
        start_total = time.time()

        cache_key = hash(user_message.strip().lower())
        if user_id in self._query_cache and cache_key in self._query_cache[user_id]:
            intent, reply = self._query_cache[user_id][cache_key]
            _logger.info(
                f"Cache hit for user {user_id} - total: {time.time() - start_total:.2f}s"
            )
            return intent, reply

        t1 = time.time()
        context = self._retrieve_context(user_message, odoo_env)
        t_retrieve = time.time() - t1

        t2 = time.time()
        messages = self._build_messages(user_id, user_message, context)
        t_build = time.time() - t2

        t3 = time.time()
        try:
            raw = self._call_ollama(messages)
            parsed = self._parse_response(raw)
        except requests.exceptions.ConnectionError:
            return (
                "error",
                "⚠️ AI service offline. Create a New Ticket for help.",
            )
        except requests.exceptions.Timeout:
            return "error", "⚠️ AI timed out. Try again."
        except Exception as e:
            _logger.error("Chatbot error: %s", e)
            return "error", "Something went wrong. Try again."

        t_llm = time.time() - t3

        intent = parsed.get("intent", "no_context")
        reply = ""

        if intent == "general":
            reply = parsed.get("reply", "")
            self._append_history(user_id, "assistant", reply)
        elif intent == "technical":
            reply = parsed.get("summary", user_message)
            self.clear_history(user_id)
        elif intent == "offtopic":
            reply = parsed.get("reply", "I can only help with Dragon Coders questions.")
        else:
            reply = parsed.get(
                "reply",
                "I don't have that information. Create a New Ticket for help.",
            )

        total_time = time.time() - start_total

        if user_id not in self._query_cache:
            self._query_cache[user_id] = {}
        self._query_cache[user_id][cache_key] = (intent, reply)

        _logger.info(
            f"Chatbot timings - user {user_id}: "
            f"retrieve: {t_retrieve:.2f}s | build: {t_build:.2f}s | "
            f"llm: {t_llm:.2f}s | total: {total_time:.2f}s"
        )

        return intent, reply

    def clear_history(self, user_id):
        self.histories.pop(user_id, None)
        self._query_cache.pop(user_id, None)

    def is_online(self):
        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return r.status_code == 200
        except Exception:
            return False

    def _retrieve_context(self, query, odoo_env):
        if not odoo_env:
            return ""
        try:
            Chunk = odoo_env["dc.knowledge.chunk"]
            chunks = Chunk.get_relevant_chunks(query, limit=3)
            if not chunks:
                return ""
            parts = []
            for chunk in chunks:
                doc_name = chunk.document_id.name
                category = chunk.document_id.category or "general"
                parts.append(f"[Source: {doc_name} | {category}]\n{chunk.content}")
            return "\n\n---\n\n".join(parts)
        except Exception as e:
            _logger.warning("Context retrieval failed: %s", e)
            return ""

    def _build_messages(self, user_id, user_message, context):
        if user_id not in self.histories:
            self.histories[user_id] = []

        user_content = (
            f"CONTEXT (answer ONLY from this):\n"
            f"{'='*50}\n{context or '[No relevant info found]'}\n{'='*50}\n\n"
            f"QUESTION: {user_message}"
        )

        history_slice = self.histories[user_id][-MAX_HISTORY:]
        messages = (
            [{"role": "system", "content": SYSTEM_PROMPT}]
            + history_slice
            + [{"role": "user", "content": user_content}]
        )

        self._append_history(user_id, "user", user_message)
        return messages

    def _append_history(self, user_id, role, content):
        if user_id not in self.histories:
            self.histories[user_id] = []
        self.histories[user_id].append({"role": role, "content": content})

    def _call_ollama(self, messages):
        response = requests.post(
            f"{self.base_url}/api/chat",
            json={
                "model": self.model,
                "messages": messages,
                "stream": False,
                "format": "json",
                "options": {
                    "temperature": 0.1,
                    "num_predict": MAX_TOKENS,
                },
            },
            timeout=60,
        )
        response.raise_for_status()
        return response.json()["message"]["content"]

    def _parse_response(self, raw):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start != -1 and end > start:
                try:
                    return json.loads(raw[start:end])
                except Exception:
                    pass
            return {"intent": "general", "reply": raw.strip()}


# ── GENERAL BOT (non-Dragon Coders questions only) ───────────────────────────
class GeneralChatBackend:
    def __init__(self, base_url=OLLAMA_BASE_URL, model=MODEL):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.histories = {}

    def send_message(self, user_id, user_message, odoo_env=None):
        general_system_prompt = """
You are a helpful general-knowledge AI assistant.

STRICT RULES:
- Answer ONLY general questions (science, history, math, definitions, explanations, fun facts, everyday topics, etc.).
- NEVER answer ANY question about Dragon Coders company, its products, services, projects, team, pricing, support, tickets, technical issues, or anything related.
- If the question is about Dragon Coders or seems company-related → reply ONLY this exact sentence: "I'm a general knowledge assistant. For questions about Dragon Coders, please use the Dragon Support chatbot or create a New Ticket."
- Keep answers concise, accurate and friendly.
- Return ONLY plain text. No JSON, no formatting.
"""

        messages = [
            {"role": "system", "content": general_system_prompt},
            {"role": "user", "content": user_message},
        ]

        try:
            response = requests.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "temperature": 0.7,
                        "num_predict": 300,
                    },
                },
                timeout=60,
            )
            response.raise_for_status()
            reply = response.json()["message"]["content"].strip()
            return "general", reply
        except Exception as e:
            _logger.error("General chat error: %s", e)
            return "error", "Sorry, something went wrong. Try again later."
