import logging
from config import CLASSIFIER_PROMPT
from .llm_client import LLMClient

logger = logging.getLogger(__name__)

VALID_INTENTS = {"add", "inquire", "update", "delete", "chitchat"}


class IntentClassifier:
    def __init__(self):
        self.llm = LLMClient()

    def classify(self, user_input: str, retries: int = 3) -> str:
        prompt = CLASSIFIER_PROMPT.format(user_input=user_input)

        for attempt in range(retries + 1):
            try:
                raw = self.llm.generate(prompt)

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
