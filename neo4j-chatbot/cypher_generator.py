import logging
from config import CYPHER_GENERATOR_PROMPT
from llm_client import LLMClient

logger = logging.getLogger(__name__)

class CypherGenerator:
    def __init__(self):
        self.llm = LLMClient()

    def _is_safe_query(self, query: str) -> bool:
        """Validates the generated Cypher query to prevent dangerous operations."""
        query_upper = query.upper()
        # Prevent full graph deletion
        if "DETACH DELETE" in query_upper and "MATCH (N)" in query_upper.replace(" ", ""):
            return False
        if "MATCH(N)DETACHDELETE" in query_upper.replace(" ", ""):
            return False
        # Prevent schema modifications
        if "DROP CONSTRAINT" in query_upper or "DROP INDEX" in query_upper:
            return False
        if "CREATE CONSTRAINT" in query_upper or "CREATE INDEX" in query_upper:
            return False
        return True

    def generate(self, user_input: str, intent: str, retries: int = 2) -> str:
        prompt = f"{CYPHER_GENERATOR_PROMPT}\\n\\nCurrent Intent: {intent}\\n\\nUser Input: {user_input}"

        for attempt in range(retries + 1):
            try:
                result = self.llm.generate(prompt)

                # Remove markdown code blocks if the LLM hallucinated them
                if result.startswith("```cypher"):
                    result = result[9:]
                elif result.startswith("```"):
                    result = result[3:]
                if result.endswith("```"):
                    result = result[:-3]
                
                result = result.strip()

                if self._is_safe_query(result):
                    return result
                
                logger.warning(f"Attempt {attempt + 1}: Generated unsafe query:\\n{result}\\nRetrying...")
            except Exception as e:
                logger.error(f"Error generating Cypher: {e}")

        raise ValueError("Failed to generate a safe & valid Cypher query after multiple attempts.")
