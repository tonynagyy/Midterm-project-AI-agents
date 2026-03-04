import logging
from config import CLASSIFIER_PROMPT
from llm_client import LLMClient

logger = logging.getLogger(__name__)

VALID_INTENTS = {"add", "inquire", "update", "delete", "chitchat"}

class IntentClassifier:
    def __init__(self):
        self.llm = LLMClient()

    def classify(self, user_input: str, retries: int = 2) -> str:
        prompt = f"{CLASSIFIER_PROMPT}\\n\\nUser Input: {user_input}"

        for attempt in range(retries + 1):
            try:
                result = self.llm.generate(prompt).strip().lower()

                # Clean up any potential markdown or extra spaces
                result = result.replace("`", "").strip()

                if result in VALID_INTENTS:
                    return result

                logger.warning(f"Attempt {attempt + 1}: Invalid intent '{result}'. Retrying...")
            except Exception as e:
                logger.error(f"Error during intent classification: {e}")

        # Fallback if all attempts fail
        logger.error(f"Failed to classify intent after {retries + 1} attempts. Defaulting to 'inquire'.")
        return "inquire"
