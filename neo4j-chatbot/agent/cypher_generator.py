import re
import logging
from config import CYPHER_GENERATOR_PROMPT, LLM_MAX_TOKENS_CYPHER
from .llm_client import LLMClient

logger = logging.getLogger(__name__)


class CypherGenerator:
    def __init__(self):
        self.llm = LLMClient()

    @staticmethod
    def _escape_cypher_string(value: str) -> str:
        return value.replace("\\", "\\\\").replace("'", "\\'")

    def _build_heuristic_query(self, user_input: str, intent: str) -> str | None:
        text = user_input.strip()
        text_no_q = text.rstrip("?").strip()

        sentence_patterns = [
            (r"^(?P<subject>.+?) plays for (?P<object>.+?)\.?$", "PLAYS_FOR"),
            (r"^(?P<subject>.+?) is from (?P<object>.+?)\.?$", "IS_FROM"),
            (r"^(?P<subject>.+?) played in the (?P<object>.+?)\.?$", "PLAYED_IN"),
        ]

        if intent == "add":
            for pattern, relation in sentence_patterns:
                match = re.match(pattern, text, flags=re.IGNORECASE)
                if not match:
                    continue

                subject = self._escape_cypher_string(match.group("subject").strip())
                obj = self._escape_cypher_string(match.group("object").strip())

                return (
                    f"MERGE (a:Node {{name: '{subject}'}})\n"
                    f"MERGE (b:Node {{name: '{obj}'}})\n"
                    f"MERGE (a)-[:{relation}]->(b)"
                )

        if intent == "inquire":
            team_player_patterns = [
                r"^who plays for (?P<team>.+)$",
                r"^which players play for (?P<team>.+)$",
                r"^show me who plays for (?P<team>.+)$",
                r"^i ask about who plays for (?P<team>.+)$",
            ]
            for pattern in team_player_patterns:
                match = re.match(pattern, text_no_q, flags=re.IGNORECASE)
                if not match:
                    continue

                team = self._escape_cypher_string(match.group("team").strip())
                return (
                    "MATCH (a:Node)-[r:PLAYS_FOR]->(b:Node)\n"
                    f"WHERE (toLower(b.name) = toLower('{team}') OR toLower(b.name) CONTAINS toLower('{team}'))\n"
                    "AND NOT toLower(a.name) = 'who'\n"
                    "AND NOT toLower(a.name) STARTS WITH 'who '\n"
                    "AND NOT toLower(a.name) CONTAINS 'ask about'\n"
                    "AND NOT toLower(a.name) STARTS WITH 'where '\n"
                    "RETURN a.name AS player, type(r) AS relation, b.name AS value\n"
                    "ORDER BY a.name\n"
                    "LIMIT 25"
                )

            play_for_patterns = [
                r"^who does (?P<subject>.+?) play for$",
                r"^what team does (?P<subject>.+?) play for$",
                r"^what team is (?P<subject>.+?) on$",
                r"^where is (?P<subject>.+?) playing$",
                r"^where does (?P<subject>.+?) play$",
            ]
            for pattern in play_for_patterns:
                match = re.match(pattern, text_no_q, flags=re.IGNORECASE)
                if not match:
                    continue

                subject = self._escape_cypher_string(match.group("subject").strip())
                return (
                    "MATCH (a:Node)-[r:PLAYS_FOR]->(b:Node)\n"
                    f"WHERE toLower(a.name) = toLower('{subject}') OR toLower(a.name) CONTAINS toLower('{subject}')\n"
                    "RETURN type(r) AS relation, b.name AS value\n"
                    "LIMIT 5"
                )

            from_patterns = [
                r"^where is (?P<subject>.+?) from$",
                r"^what country is (?P<subject>.+?) from$",
            ]
            for pattern in from_patterns:
                match = re.match(pattern, text_no_q, flags=re.IGNORECASE)
                if not match:
                    continue

                subject = self._escape_cypher_string(match.group("subject").strip())
                return (
                    "MATCH (a:Node)-[r:IS_FROM]->(b:Node)\n"
                    f"WHERE toLower(a.name) = toLower('{subject}') OR toLower(a.name) CONTAINS toLower('{subject}')\n"
                    "RETURN type(r) AS relation, b.name AS value\n"
                    "LIMIT 5"
                )

        return None

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

    def _matches_intent_shape(self, query: str, intent: str) -> bool:
        q_upper = query.upper()

        if intent == "inquire":
            forbidden = ("DELETE", "DETACH DELETE", "MERGE", "CREATE", "SET")
            return not any(token in q_upper for token in forbidden)

        if intent == "add":
            return "MERGE" in q_upper and "DELETE" not in q_upper

        return True

    def generate(
        self,
        user_input: str,
        intent: str,
        memory_context: str = "",
        retries: int = 3,
    ) -> str:
        heuristic_query = self._build_heuristic_query(user_input=user_input, intent=intent)
        if heuristic_query:
            logger.debug("Using heuristic Cypher query for intent '%s'.", intent)
            return heuristic_query

        prompt = CYPHER_GENERATOR_PROMPT.format(
            intent=intent,
            user_input=user_input,
            memory_context=memory_context or "None",
        )

        for attempt in range(retries + 1):
            try:
                raw = self.llm.generate(
                    prompt,
                    max_tokens=LLM_MAX_TOKENS_CYPHER,
                )
                result = self._clean_query(raw)

                if not result:
                    logger.warning(f"Attempt {attempt + 1}: Empty query returned.")
                    continue

                if not self._matches_intent_shape(result, intent):
                    logger.warning(
                        "Attempt %s: Query shape does not match intent '%s'. Retrying...",
                        attempt + 1,
                        intent,
                    )
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
