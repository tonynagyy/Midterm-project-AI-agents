import logging
import re
from config import CLASSIFIER_PROMPT, LLM_MAX_TOKENS_CLASSIFIER
from .llm_client import LLMClient

logger = logging.getLogger(__name__)

VALID_INTENTS = {"add", "inquire", "update", "delete", "chitchat"}


class IntentClassifier:
    def __init__(self):
        self.llm = LLMClient()

    @staticmethod
    def _heuristic_classify(user_input: str) -> str | None:
        text = (user_input or "").strip()
        if not text:
            return None

        lowered = text.lower()
        lowered_no_q = lowered.rstrip("?").strip()

        # Question-like utterances must win over declarative fact patterns.
        if text.endswith("?"):
            return "inquire"

        if re.match(
            r"^(who|what|where|which|when|does|is|are|can|could|would|do|did)\b",
            lowered_no_q,
        ):
            return "inquire"

        if re.search(
            r"\b(who plays for|who does .+ play for|where is .+ from|where is .+ playing|where does .+ play)\b",
            lowered_no_q,
        ):
            return "inquire"

        if re.match(r"^(tell me|show me|i ask about|im asking about|i am asking about)\b", lowered_no_q):
            if re.search(r"\b(who|what|where|which)\b", lowered_no_q):
                return "inquire"

        # Declarative fact statements should always be treated as add.
        fact_patterns = [
            r"^.+?\splays for\s.+$",
            r"^.+?\sis from\s.+$",
            r"^.+?\splayed in the\s.+$",
        ]
        if any(re.match(pattern, lowered_no_q) for pattern in fact_patterns):
            return "add"

        if re.match(r"^(add|insert|remember|store)\b", lowered_no_q):
            return "add"

        if re.match(r"^(update|change|modify|set)\b", lowered_no_q):
            return "update"

        if re.match(r"^(delete|remove)\b", lowered_no_q):
            return "delete"

        if re.match(r"^(hi|hello|hey|thanks|thank you)\b", lowered_no_q):
            return "chitchat"

        return None

    def classify(
        self,
        user_input: str,
        memory_context: str = "",
        retries: int = 3,
    ) -> str:
        heuristic_intent = self._heuristic_classify(user_input)
        if heuristic_intent:
            logger.info("Intent classified by heuristic as '%s'.", heuristic_intent)
            return heuristic_intent

        prompt = CLASSIFIER_PROMPT.format(
            user_input=user_input,
            memory_context=memory_context or "None",
        )

        for attempt in range(retries + 1):
            try:
                raw = self.llm.generate(
                    prompt,
                    max_tokens=LLM_MAX_TOKENS_CLASSIFIER,
                )

                result = raw.strip().lower()
                result = result.replace("`", "").replace(".", "").replace("'", "").strip()

                for intent in VALID_INTENTS:
                    if result == intent:
                        return result
                    if result.endswith(intent):
                        return intent
                    if result.startswith(intent):
                        return intent

                logger.warning(
                    f"Attempt {attempt + 1}: Invalid intent '{raw.strip()}'. Retrying..."
                )
            except Exception as e:
                logger.error(f"Error during intent classification (attempt {attempt + 1}): {e}")

        logger.error(
            f"Failed to classify intent after {retries + 1} attempts. Defaulting to 'inquire'."
        )
        return "inquire"
