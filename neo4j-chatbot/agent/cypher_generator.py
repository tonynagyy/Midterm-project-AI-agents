import re
import logging
from config import CYPHER_GENERATOR_PROMPT
from .llm_client import LLMClient

logger = logging.getLogger(__name__)


class CypherGenerator:
    def __init__(self):
        self.llm = LLMClient()

    def _clean_query(self, raw: str) -> str:
        """Strip markdown fences, leading labels, and extra whitespace."""
        text = raw.strip()

        # Remove ```cypher ... ``` or ``` ... ``` fences
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
        text = text.strip()

        # Remove lines that are purely explanatory (start with # or //)
        lines = text.splitlines()
        lines = [l for l in lines if not l.strip().startswith(("//", "#"))]
        text = "\n".join(lines).strip()

        return text

    def _is_safe_query(self, query: str) -> bool:
        """Validates the generated Cypher query to prevent dangerous operations."""
        q = query.upper().replace(" ", "")

        # Prevent full graph deletion
        if "MATCH(N)DETACHDELETE" in q or "MATCH(N)DELETE" in q:
            return False
        # Prevent schema modifications
        forbidden = ["DROPCONSTRAINT", "DROPINDEX", "CREATECONSTRAINT", "CREATEINDEX"]
        if any(f in q for f in forbidden):
            return False
        # Must contain at least one valid Cypher keyword
        valid_starts = ("MATCH", "MERGE", "CREATE", "CALL", "WITH")
        if not any(query.strip().upper().startswith(k) for k in valid_starts):
            return False
        return True

    def generate(self, user_input: str, intent: str, retries: int = 3) -> str:
        prompt = CYPHER_GENERATOR_PROMPT.format(intent=intent, user_input=user_input)

        for attempt in range(retries + 1):
            try:
                raw = self.llm.generate(prompt)
                result = self._clean_query(raw)

                if not result:
                    logger.warning(f"Attempt {attempt + 1}: Empty query returned.")
                    continue

                if self._is_safe_query(result):
                    logger.debug(f"Generated Cypher:\n{result}")
                    return result

                logger.warning(
                    f"Attempt {attempt + 1}: Unsafe query rejected:\n{result}\nRetrying..."
                )
            except Exception as e:
                logger.error(f"Error generating Cypher (attempt {attempt + 1}): {e}")

        raise ValueError(
            f"Failed to generate a safe & valid Cypher query after {retries + 1} attempts."
        )
