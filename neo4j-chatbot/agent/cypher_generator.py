import re
import logging
from typing import Any

from neo4j import GraphDatabase

from config import (
    CYPHER_GENERATOR_PROMPT,
    LLM_MAX_TOKENS_CYPHER,
    LLM_MODEL_CYPHER,
    NEO4J_PASSWORD,
    NEO4J_URI,
    NEO4J_USER,
)
from .llm_client import LLMClient

logger = logging.getLogger(__name__)


class CypherGenerator:
    RELATION_TYPE_BY_PHRASE = {
        "plays for": "PLAYS_FOR",
        "is from": "IS_FROM",
        "played in the": "PLAYED_IN",
        "has position": "HAS_POSITION",
        "position is": "HAS_POSITION",
    }

    RELATION_TYPE_BY_FIELD = {
        "team": "PLAYS_FOR",
        "club": "PLAYS_FOR",
        "position": "HAS_POSITION",
        "country": "IS_FROM",
        "nationality": "IS_FROM",
        "origin": "IS_FROM",
    }

    def __init__(self):
        self.llm = LLMClient()
        self.cypher_model = LLM_MODEL_CYPHER or None
        self._repair_driver: Any | None = None
        self._repair_enabled = True

    @staticmethod
    def _escape_cypher_string(value: str) -> str:
        return value.replace("\\", "\\\\").replace("'", "\\'")

    @staticmethod
    def _normalize_entity(value: str) -> str:
        return re.sub(r'^["\']|["\']$', "", value.strip())

    def _build_deterministic_query(self, user_input: str, intent: str) -> str | None:
        if intent == "add":
            return self._build_add_query(user_input)
        if intent == "update":
            return self._build_update_query(user_input)
        if intent == "delete":
            return self._build_delete_query(user_input)
        return None

    def _build_add_query(self, user_input: str) -> str | None:
        text = user_input.strip()
        text = re.sub(
            r"^(?:add(?: the fact that)?|remember|store)\s+(?:that\s+)?",
            "",
            text,
            flags=re.IGNORECASE,
        ).strip()
        text = text.rstrip(".").strip()

        sentence_patterns = [
            (r"^(?P<subject>.+?) plays for (?P<object>.+)$", "PLAYS_FOR"),
            (r"^(?P<subject>.+?) is from (?P<object>.+)$", "IS_FROM"),
            (r"^(?P<subject>.+?) played in the (?P<object>.+)$", "PLAYED_IN"),
            (r"^(?P<subject>.+?) has position (?P<object>.+)$", "HAS_POSITION"),
            (r"^(?P<subject>.+?) position is (?P<object>.+)$", "HAS_POSITION"),
        ]

        for pattern, relation in sentence_patterns:
            match = re.match(pattern, text, flags=re.IGNORECASE)
            if not match:
                continue

            subject = self._escape_cypher_string(
                self._normalize_entity(match.group("subject"))
            )
            obj = self._escape_cypher_string(self._normalize_entity(match.group("object")))

            return (
                f"MERGE (a:Node {{name: '{subject}'}})\n"
                f"MERGE (b:Node {{name: '{obj}'}})\n"
                f"MERGE (a)-[:{relation}]->(b)"
            )

        return None

    def _build_update_query(self, user_input: str) -> str | None:
        text = user_input.strip().rstrip(".").strip()

        relation_update_patterns = [
            r"^(?:update|change|modify|set)\s+(?:the fact that\s+)?(?P<subject>.+?)\s+(?P<relation>plays for|is from|has position|played in the)\s+(?P<old>.+?)\s+to\s+(?P<new>.+)$",
            r"^(?:update|change|modify|set)\s+(?P<subject>.+?)\s+(?P<relation>plays for|is from|has position|played in the)\s+to\s+(?P<new>.+)$",
        ]

        for pattern in relation_update_patterns:
            match = re.match(pattern, text, flags=re.IGNORECASE)
            if not match:
                continue

            relation = self.RELATION_TYPE_BY_PHRASE.get(
                match.group("relation").lower().strip()
            )
            if not relation:
                continue

            subject = self._escape_cypher_string(
                self._normalize_entity(match.group("subject"))
            )
            new_value = self._escape_cypher_string(self._normalize_entity(match.group("new")))
            old_value = match.groupdict().get("old")
            old_value = (
                self._escape_cypher_string(self._normalize_entity(old_value))
                if old_value
                else ""
            )

            return self._build_update_relation_query(
                subject=subject,
                relation=relation,
                new_value=new_value,
                old_value=old_value,
            )

        field_update_patterns = [
            r"^(?:update|change|modify|set)\s+(?P<subject>.+?)(?:'s)?\s+(?P<field>team|club|position|country|nationality|origin)\s+from\s+(?P<old>.+?)\s+to\s+(?P<new>.+)$",
            r"^(?:update|change|modify|set)\s+(?P<subject>.+?)(?:'s)?\s+(?P<field>team|club|position|country|nationality|origin)\s+(?:to|as)\s+(?P<new>.+)$",
        ]

        for pattern in field_update_patterns:
            match = re.match(pattern, text, flags=re.IGNORECASE)
            if not match:
                continue

            relation = self.RELATION_TYPE_BY_FIELD.get(match.group("field").lower().strip())
            if not relation:
                continue

            subject = self._escape_cypher_string(
                self._normalize_entity(match.group("subject"))
            )
            new_value = self._escape_cypher_string(self._normalize_entity(match.group("new")))
            old_value = match.groupdict().get("old")
            old_value = (
                self._escape_cypher_string(self._normalize_entity(old_value))
                if old_value
                else ""
            )

            return self._build_update_relation_query(
                subject=subject,
                relation=relation,
                new_value=new_value,
                old_value=old_value,
            )

        return None

    def _build_delete_query(self, user_input: str) -> str | None:
        text = user_input.strip().rstrip(".").strip()

        relation_delete_patterns = [
            r"^(?:delete|remove)\s+(?:the\s+)?(?:relation|fact)\s+(?:that\s+)?(?P<subject>.+?)\s+(?P<relation>plays for|is from|has position|played in the)\s+(?P<object>.+)$",
            r"^(?:delete|remove)\s+(?:that\s+)?(?P<subject>.+?)\s+(?P<relation>plays for|is from|has position|played in the)\s+(?P<object>.+)$",
        ]

        for pattern in relation_delete_patterns:
            match = re.match(pattern, text, flags=re.IGNORECASE)
            if not match:
                continue

            relation = self.RELATION_TYPE_BY_PHRASE.get(
                match.group("relation").lower().strip()
            )
            if not relation:
                continue

            subject = self._escape_cypher_string(
                self._normalize_entity(match.group("subject"))
            )
            obj = self._escape_cypher_string(self._normalize_entity(match.group("object")))
            return (
                f"MATCH (a:Node {{name: '{subject}'}})-[r:{relation}]->(b:Node {{name: '{obj}'}})\n"
                "DELETE r"
            )

        subject_relation_delete_pattern = (
            r"^(?:delete|remove)\s+(?P<subject>.+?)\s+"
            r"(?P<field>team|club|position|country|nationality|origin)\s+fact$"
        )
        match = re.match(subject_relation_delete_pattern, text, flags=re.IGNORECASE)
        if match:
            relation = self.RELATION_TYPE_BY_FIELD.get(match.group("field").lower().strip())
            if relation:
                subject = self._escape_cypher_string(
                    self._normalize_entity(match.group("subject"))
                )
                return (
                    f"MATCH (a:Node {{name: '{subject}'}})-[r:{relation}]->(:Node)\n"
                    "DELETE r"
                )

        delete_node_pattern = r"^(?:delete|remove)\s+(?:node\s+)?(?P<subject>.+)$"
        match = re.match(delete_node_pattern, text, flags=re.IGNORECASE)
        if match:
            subject_value = self._normalize_entity(match.group("subject"))
            if any(token in subject_value.lower() for token in ["relation", "fact", " to "]):
                return None
            subject = self._escape_cypher_string(subject_value)
            return (
                f"MATCH (a:Node {{name: '{subject}'}})\n"
                "DETACH DELETE a"
            )

        return None

    def _build_update_relation_query(
        self,
        subject: str,
        relation: str,
        new_value: str,
        old_value: str,
    ) -> str:
        if old_value:
            return (
                f"MATCH (a:Node {{name: '{subject}'}})-[r:{relation}]->(b:Node {{name: '{old_value}'}})\n"
                "DELETE r\n"
                "WITH a\n"
                f"MERGE (c:Node {{name: '{new_value}'}})\n"
                f"MERGE (a)-[:{relation}]->(c)"
            )

        return (
            f"MATCH (a:Node {{name: '{subject}'}})-[r:{relation}]->(:Node)\n"
            "DELETE r\n"
            "WITH a\n"
            f"MERGE (c:Node {{name: '{new_value}'}})\n"
            f"MERGE (a)-[:{relation}]->(c)"
        )

    def _build_inquire_heuristic_query(self, user_input: str) -> str | None:
        text = user_input.strip()
        text_no_q = text.rstrip("?").strip()

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

    def _build_fallback_inquire_query(self, user_input: str) -> str:
        text = user_input.strip().rstrip("?").strip()
        subject_patterns = [
            r"\bfor\s+(?P<subject>.+)$",
            r"\babout\s+(?P<subject>.+)$",
            r"\blinked to\s+(?P<subject>.+)$",
            r"\bof\s+(?P<subject>.+)$",
        ]

        subject = ""
        for pattern in subject_patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                subject = self._normalize_entity(match.group("subject"))
                break

        if not subject:
            subject = text

        subject = self._escape_cypher_string(subject)
        return (
            "MATCH (a:Node)-[r]->(b:Node)\n"
            f"WHERE toLower(a.name) CONTAINS toLower('{subject}') "
            f"OR toLower(b.name) CONTAINS toLower('{subject}')\n"
            "RETURN a.name AS source, type(r) AS relation, b.name AS value\n"
            "LIMIT 25"
        )

    def _sanitize_llm_noise(self, text: str) -> str:
        sanitized = text

        # Remove formatter artifacts frequently emitted by small finetuned models.
        sanitized = re.sub(r"\{[A-Za-z_][A-Za-z0-9_]*:\.[^{}]*\}", "", sanitized)
        sanitized = re.sub(r"<\|fim_[^|]+\|>", "", sanitized)
        sanitized = re.sub(r"</?lemma>", "", sanitized, flags=re.IGNORECASE)
        sanitized = re.sub(r"\bask:[^\s]+", "", sanitized)
        sanitized = re.sub(r"\bbatchSize\s+\d+", "", sanitized, flags=re.IGNORECASE)
        sanitized = re.sub(r"/documentation/\S+", "", sanitized)

        return sanitized.strip()

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

        text = re.sub(r"^\s*cypher\s*:\s*", "", text, flags=re.IGNORECASE).strip()
        text = self._sanitize_llm_noise(text)

        return text

    def _build_repair_candidates(self, query: str) -> list[str]:
        candidates: list[str] = []
        seen: set[str] = set()

        def add_candidate(value: str) -> None:
            candidate = value.strip().strip(";").strip()
            if not candidate or candidate in seen:
                return
            seen.add(candidate)
            candidates.append(candidate)

        add_candidate(query)
        add_candidate(re.sub(r"\{[A-Za-z_][A-Za-z0-9_]*:\.[^{}]*\}", "", query))

        if ";" in query:
            add_candidate(query.split(";", 1)[0])

        for marker in ("<|", "ask:", " batchSize ", "/documentation/"):
            marker_index = query.find(marker)
            if marker_index > 0:
                add_candidate(query[:marker_index])

        upper = query.upper()
        keyword_positions = [
            upper.find("MATCH"),
            upper.find("MERGE"),
            upper.find("WITH"),
            upper.find("CALL"),
            upper.find("CREATE"),
        ]
        keyword_positions = [position for position in keyword_positions if position >= 0]
        if keyword_positions:
            first_keyword_index = min(keyword_positions)
            if first_keyword_index > 0:
                add_candidate(query[first_keyword_index:])

        lines = [line.strip() for line in query.splitlines() if line.strip()]
        if lines:
            add_candidate(lines[0])
            min_line_count = max(1, len(lines) - 3)
            for keep_count in range(len(lines), min_line_count - 1, -1):
                add_candidate("\n".join(lines[:keep_count]))

        tokens = query.split()
        for trim_count in (1, 2, 3, 5, 8, 12):
            if len(tokens) - trim_count >= 3:
                add_candidate(" ".join(tokens[:-trim_count]))

        return candidates

    def _ensure_repair_driver(self):
        if not self._repair_enabled:
            return None

        if self._repair_driver is not None:
            return self._repair_driver

        try:
            driver = GraphDatabase.driver(
                NEO4J_URI,
                auth=(NEO4J_USER, NEO4J_PASSWORD),
            )
            driver.verify_connectivity()
            self._repair_driver = driver
            return self._repair_driver
        except Exception as exc:  # pragma: no cover
            self._repair_enabled = False
            logger.warning(
                "Cypher EXPLAIN validation disabled because Neo4j is unavailable: %s",
                exc,
            )
            return None

    def _explain_parse(self, driver, query: str) -> tuple[bool, str]:
        try:
            with driver.session() as session:
                session.run("EXPLAIN " + query).consume()
            return True, ""
        except Exception as exc:  # pragma: no cover
            return False, str(exc)

    def _select_valid_candidate(self, query: str, intent: str) -> tuple[str | None, str]:
        candidates = self._build_repair_candidates(query)
        if not candidates:
            return None, "No Cypher candidate generated"

        driver = self._ensure_repair_driver()
        explain_enabled = driver is not None
        last_explain_error = ""

        for candidate in candidates:
            if not self._matches_intent_shape(candidate, intent):
                continue
            if not self._is_safe_query(candidate):
                continue

            if not explain_enabled:
                return candidate, ""

            explain_ok, explain_error = self._explain_parse(driver, candidate)
            if explain_ok:
                return candidate, ""
            last_explain_error = explain_error

        return None, last_explain_error

    def _build_repair_prompt(self, query: str, intent: str, explain_error: str) -> str:
        return (
            "Fix this Neo4j Cypher query so EXPLAIN succeeds.\n\n"
            "Rules:\n"
            "- Return exactly one Cypher statement only.\n"
            "- No markdown, no comments, no explanation.\n"
            "- Use Node label and name property only.\n"
            "- Keep intent-safe semantics.\n"
            "- Never use schema DDL or full-graph deletion.\n\n"
            f"Intent: {intent}\n"
            f"EXPLAIN Error: {explain_error or 'Unknown syntax error'}\n"
            f"Broken Query:\n{query}\n\n"
            "Corrected Cypher:"
        )

    def _repair_and_validate(
        self,
        query_text: str,
        intent: str,
        model_override: str | None,
    ) -> tuple[str | None, str]:
        cleaned = self._clean_query(query_text)
        if not cleaned:
            return None, "Empty query returned"

        selected_query, explain_error = self._select_valid_candidate(cleaned, intent)
        if selected_query:
            return selected_query, ""

        repair_prompt = self._build_repair_prompt(
            query=cleaned,
            intent=intent,
            explain_error=explain_error,
        )

        repaired_raw = self.llm.generate(
            repair_prompt,
            max_tokens=LLM_MAX_TOKENS_CYPHER,
            model=model_override,
        )
        repaired_cleaned = self._clean_query(repaired_raw)
        if not repaired_cleaned:
            return None, explain_error or "Repair pass produced an empty query"

        repaired_query, repaired_error = self._select_valid_candidate(
            repaired_cleaned,
            intent,
        )
        if repaired_query:
            return repaired_query, ""

        return None, repaired_error or explain_error or "Cypher repair failed"

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

        if intent == "update":
            return "MERGE" in q_upper and "DELETE" in q_upper

        if intent == "delete":
            return "DELETE" in q_upper

        return True

    def close(self) -> None:
        if self._repair_driver is None:
            return
        try:
            self._repair_driver.close()
        except Exception:  # pragma: no cover
            pass
        finally:
            self._repair_driver = None

    def generate(
        self,
        user_input: str,
        intent: str,
        memory_context: str = "",
        retries: int = 3,
    ) -> str:
        normalized_intent = (intent or "inquire").strip().lower()

        deterministic_query = self._build_deterministic_query(
            user_input=user_input,
            intent=normalized_intent,
        )
        if deterministic_query:
            logger.debug("Using deterministic Cypher template for intent '%s'.", normalized_intent)
            return deterministic_query

        if normalized_intent in {"add", "update", "delete"}:
            raise ValueError(
                f"Could not deterministically parse {normalized_intent} request. "
                "Please use explicit subject-relation-object phrasing."
            )

        heuristic_query = self._build_inquire_heuristic_query(user_input=user_input)
        if heuristic_query:
            logger.debug("Using heuristic Cypher query for intent '%s'.", normalized_intent)
            return heuristic_query

        prompt = CYPHER_GENERATOR_PROMPT.format(
            intent=normalized_intent,
            user_input=user_input,
            memory_context=memory_context or "None",
        )
        model_override = self.cypher_model if normalized_intent == "inquire" else None
        last_error = ""

        for attempt in range(retries + 1):
            try:
                raw = self.llm.generate(
                    prompt,
                    max_tokens=LLM_MAX_TOKENS_CYPHER,
                    model=model_override,
                )
                result, error_reason = self._repair_and_validate(
                    query_text=raw,
                    intent=normalized_intent,
                    model_override=model_override,
                )
                if result:
                    logger.debug("Generated Cypher:\n%s", result)
                    return result

                last_error = error_reason
                logger.warning(
                    "Attempt %s: Cypher validation/repair failed for intent '%s': %s",
                    attempt + 1,
                    normalized_intent,
                    error_reason,
                )
            except Exception as e:
                last_error = str(e)
                logger.error(f"Error generating Cypher (attempt {attempt + 1}): {e}")

        if normalized_intent == "inquire":
            fallback_query = self._build_fallback_inquire_query(user_input=user_input)
            selected_fallback, fallback_error = self._select_valid_candidate(
                fallback_query,
                normalized_intent,
            )
            if selected_fallback:
                logger.warning(
                    "Using deterministic inquire fallback after model retries failed."
                )
                return selected_fallback
            if fallback_error:
                last_error = fallback_error

        raise ValueError(
            f"Failed to generate a safe & valid Cypher query after {retries + 1} attempts."
            + (f" Last error: {last_error}" if last_error else "")
        )
