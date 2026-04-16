import logging
import re
from config import (
    RESPONSE_ENGINE_PROMPT,
    LLM_MAX_TOKENS_RESPONSE,
    LLM_MAX_TOKENS_CHITCHAT,
)
from .llm_client import LLMClient

logger = logging.getLogger(__name__)


class ResponseEngine:
    def __init__(self):
        self.llm = LLMClient()

    @staticmethod
    def _join_names(items: list[str]) -> str:
        unique = []
        seen = set()
        for item in items:
            text = str(item).strip()
            if not text:
                continue
            key = text.lower()
            if key in seen:
                continue
            seen.add(key)
            unique.append(text)

        if not unique:
            return ""
        if len(unique) == 1:
            return unique[0]
        if len(unique) == 2:
            return f"{unique[0]} and {unique[1]}"
        return ", ".join(unique[:-1]) + f", and {unique[-1]}"

    @staticmethod
    def _relation_to_phrase(relation: str) -> str:
        mapping = {
            "PLAYS_FOR": "plays for",
            "IS_FROM": "is from",
            "PLAYED_IN": "played in",
        }
        return mapping.get((relation or "").upper(), "is related to")

    @staticmethod
    def _extract_subject_from_question(user_input: str) -> str:
        text = (user_input or "").strip().rstrip("?")
        patterns = [
            r"^who does (?P<subject>.+?) play for$",
            r"^what team does (?P<subject>.+?) play for$",
            r"^what team is (?P<subject>.+?) on$",
            r"^where is (?P<subject>.+?) playing$",
            r"^where does (?P<subject>.+?) play$",
            r"^where is (?P<subject>.+?) from$",
            r"^what country is (?P<subject>.+?) from$",
        ]

        for pattern in patterns:
            match = re.match(pattern, text, flags=re.IGNORECASE)
            if match:
                return match.group("subject").strip()

        return ""

    def _deterministic_inquire_response(self, user_input: str, db_results: list) -> str | None:
        if not db_results:
            return "No results found."

        if all(isinstance(row, dict) and "player" in row and "value" in row for row in db_results):
            team = str(db_results[0].get("value", "")).strip()
            players = [str(row.get("player", "")).strip() for row in db_results]
            player_text = self._join_names(players)
            if player_text and team:
                return f"{player_text} play for {team}."

        if all(isinstance(row, dict) and "relation" in row and "value" in row for row in db_results):
            relation = str(db_results[0].get("relation", "")).strip()
            phrase = self._relation_to_phrase(relation)

            values = [str(row.get("value", "")).strip() for row in db_results]
            value_text = self._join_names(values)

            subject = self._extract_subject_from_question(user_input)
            if subject and value_text:
                return f"{subject} {phrase} {value_text}."

            if value_text:
                return value_text

        return None

    def generate_response(
        self,
        user_input: str,
        db_results: list,
        action_msg: str,
        intent: str,
        memory_context: str = "",
    ) -> str:
        """Converts raw Neo4j results into a natural language response."""

        if intent in {"add", "update", "delete"}:
            return f"{action_msg} successfully."

        if intent == "inquire":
            deterministic = self._deterministic_inquire_response(user_input, db_results)
            if deterministic is not None:
                return deterministic

        db_results_str = str(db_results) if db_results else "No results found."

        prompt = RESPONSE_ENGINE_PROMPT.format(
            user_input=user_input,
            memory_context=memory_context or "None",
            db_results=db_results_str,
            action_msg=action_msg,
            intent=intent,
        )

        try:
            generated = self.llm.generate(
                prompt,
                max_tokens=LLM_MAX_TOKENS_RESPONSE,
            )
            if generated and generated.strip():
                return generated.strip()
            logger.warning("LLM returned empty response for intent '%s'.", intent)
            return "I could not find enough information to answer that clearly."
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return "I encountered an error while formulating the response."

    def generate_chitchat(self, user_input: str, memory_context: str = "") -> str:
        """Handles casual conversation without touching the database."""
        prompt = (
            "You are a friendly football chatbot specializing in the Champions League. "
            "The user is making casual conversation. Reply warmly in exactly 1 short sentence (max 15 words).\n\n"
            f"Recent conversation:\n{memory_context or 'None'}\n\n"
            f"User: {user_input}\n"
            "Bot:"
        )
        try:
            generated = self.llm.generate(
                prompt,
                max_tokens=LLM_MAX_TOKENS_CHITCHAT,
            )
            if generated and generated.strip():
                return generated.strip()
            logger.warning("LLM returned empty chitchat response.")
            return "Hello! How can I help you with Champions League knowledge today?"
        except Exception as e:
            logger.error(f"Error generating chitchat response: {e}")
            return "Hello! How can I help you with Champions League knowledge today?"
