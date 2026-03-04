import logging
from config import RESPONSE_ENGINE_PROMPT
from llm_client import LLMClient

logger = logging.getLogger(__name__)

class ResponseEngine:
    def __init__(self):
        self.llm = LLMClient()

    def generate_response(self, user_input: str, db_results: list) -> str:
        """Takes the user's input and raw database results and generates a conversational,
        non-hallucinated response."""
        
        db_results_str = str(db_results) if db_results else "No results found."

        prompt = RESPONSE_ENGINE_PROMPT.format(user_input=user_input, db_results=db_results_str)
        
        try:
            return self.llm.generate(prompt)
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return "I apologize, but I encountered an error while formulating your response."

    def generate_chitchat(self, user_input: str) -> str:
        """Handles chitchat without needing database results."""
        prompt = (
            "You are a helpful and polite football chatbot that knows about the Champions League. "
            "The user just said something conversational. Respond briefly and politely.\\n\\n"
            f"User: {user_input}\\nBot:"
        )
        
        try:
            return self.llm.generate(prompt)
        except Exception as e:
            logger.error(f"Error generating chitchat response: {e}")
            return "Hello! How can I assist you with Champions League football knowledge?"
