import logging
from config import RESPONSE_ENGINE_PROMPT
from .llm_client import LLMClient

logger = logging.getLogger(__name__)


class ResponseEngine:
    def __init__(self):
        self.llm = LLMClient()

    def generate_response(
        self, user_input: str, db_results: list, action_msg: str, intent: str
    ) -> str:
        """Converts raw Neo4j results into a natural language response."""

        db_results_str = str(db_results) if db_results else "No results found."

        prompt = RESPONSE_ENGINE_PROMPT.format(
            user_input=user_input,
            db_results=db_results_str,
            action_msg=action_msg,
            intent=intent,
        )

        try:
            return self.llm.generate(prompt)
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return "I encountered an error while formulating the response."

    def generate_chitchat(self, user_input: str) -> str:
        """Handles casual conversation without touching the database."""
        prompt = (
            "You are a friendly football chatbot specializing in the Champions League. "
            "The user is making casual conversation. Reply warmly in 1-2 sentences.\n\n"
            f"User: {user_input}\n"
            "Bot:"
        )
        try:
            return self.llm.generate(prompt)
        except Exception as e:
            logger.error(f"Error generating chitchat response: {e}")
            return "Hello! How can I help you with Champions League knowledge today?"
