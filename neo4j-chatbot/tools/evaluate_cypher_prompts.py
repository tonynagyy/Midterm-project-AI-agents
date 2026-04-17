import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from neo4j import GraphDatabase

from agent.cypher_generator import CypherGenerator
from agent.llm_client import LLMClient
from config import (
    CYPHER_GENERATOR_PROMPT,
    LLM_MAX_TOKENS_CYPHER,
    LLM_MODEL,
    LLM_MODEL_CYPHER,
    NEO4J_PASSWORD,
    NEO4J_URI,
    NEO4J_USER,
)


PROMPT_VARIANTS: Dict[str, str] = {
    "baseline": CYPHER_GENERATOR_PROMPT,
    "compact_text2cypher": """You are a text2cypher model.

Schema:
- Nodes: (:Node {{name: string}})
- Facts: (:Node)-[:RELATION_TYPE]->(:Node)

Intent: {intent}
Context: {memory_context}
Input: {user_input}

Rules:
- Output exactly one Cypher statement only.
- Use label Node and property name only.
- [add] MERGE nodes and MERGE relation.
- [inquire] MATCH and RETURN data only.
- [update] MATCH old relation, DELETE it, then MERGE new relation.
- [delete] MATCH and DELETE relation or DETACH DELETE one named node.
- No markdown, no backticks, no explanation.
- Never delete the full graph.
- Never create/drop indexes or constraints.

Cypher:""",
    "schema_locked_text2cypher": """### Task
Convert user intent to safe Neo4j Cypher.

### Graph Schema
(:Node {{name}})-[:REL]->(:Node {{name}})

### Intent
{intent}

### Conversation
{memory_context}

### User Request
{user_input}

### Hard Constraints
1) Output only raw Cypher.
2) One statement only.
3) Always use Node label and name property.
4) Never use schema DDL.
5) Never use MATCH (n) DETACH DELETE n.
6) Keep query minimal and executable.

### Intent Mapping
- add: MERGE/MERGE/MERGE
- inquire: MATCH...RETURN
- update: MATCH old rel, DELETE old rel, MERGE new rel
- delete: MATCH...DELETE or named-node DETACH DELETE

### Cypher Output
""",
    "strict_single_statement": """You are a Neo4j text2cypher model.

Schema:
(:Node {{name}})-[:RELATION_TYPE]->(:Node {{name}})

Intent: {intent}
Conversation: {memory_context}
User input: {user_input}

Rules:
- Output exactly one Cypher statement with no explanation.
- Use only Node label and name property.
- Keep relation types uppercase with underscores.
- Never use UNION.
- Never output schema operations.
- Never output full graph deletion.

Intent templates:
- add: MERGE subject node, MERGE object node, MERGE relationship.
- inquire: MATCH with optional WHERE and RETURN relation/value.
- update: MATCH old relationship, DELETE old relationship, MERGE new relationship.
- delete: MATCH target relationship and DELETE it, or DETACH DELETE one named node.

Return only raw Cypher now:
""",
    "template_fill_only": """Fill exactly one Cypher template based on intent.

Schema:
(:Node {{name}})-[:RELATION_TYPE]->(:Node {{name}})

Intent: {intent}
User input: {user_input}
Context: {memory_context}

Templates:
add:
MERGE (a:Node {{name: '<subject>'}})
MERGE (b:Node {{name: '<object>'}})
MERGE (a)-[:<RELATION_TYPE>]->(b)

inquire:
MATCH (a:Node)-[r]->(b:Node)
WHERE toLower(a.name) CONTAINS toLower('<subject>')
RETURN type(r) AS relation, b.name AS value
LIMIT 25

update:
MATCH (a:Node)-[r:<RELATION_TYPE>]->(b:Node {{name: '<old_object>'}})
DELETE r
WITH a
MERGE (c:Node {{name: '<new_object>'}})
MERGE (a)-[:<RELATION_TYPE>]->(c)

delete:
MATCH (a:Node {{name: '<subject>'}})-[r:<RELATION_TYPE>]->(b:Node {{name: '<object>'}})
DELETE r

Rules:
- Output one Cypher statement only.
- Replace placeholders from user input.
- Do not output markdown, comments, explanation, or extra text.
- Do not use UNION.
- Do not use schema DDL.
""",
}

CASES: List[Dict[str, str]] = [
    {"intent": "inquire", "user_input": "Find all known relations for Lionel Messi"},
    {"intent": "inquire", "user_input": "Show knowledge linked to Arsenal players"},
    {"intent": "add", "user_input": "Add that Pedri has position Midfielder"},
    {"intent": "update", "user_input": "Update Bukayo Saka team to Arsenal FC"},
    {"intent": "delete", "user_input": "Delete the relation that Rodri is from Spain"},
    {"intent": "delete", "user_input": "Remove Pedri position fact"},
]


def _explain_parse(driver: Any, query: str) -> Tuple[bool, str]:
    try:
        with driver.session() as session:
            session.run("EXPLAIN " + query).consume()
        return True, ""
    except Exception as exc:  # pragma: no cover
        return False, str(exc)


def _evaluate_variant(
    name: str,
    prompt_template: str,
    llm: LLMClient,
    helper: CypherGenerator,
    driver: Any,
    model_name: str,
) -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []

    for case in CASES:
        intent = case["intent"]
        user_input = case["user_input"]
        prompt = prompt_template.format(
            intent=intent,
            user_input=user_input,
            memory_context="None",
        )

        started = time.perf_counter()
        raw = ""
        error = ""

        try:
            raw = llm.generate(
                prompt,
                max_tokens=LLM_MAX_TOKENS_CYPHER,
                model=model_name,
            )
        except Exception as exc:
            error = str(exc)

        latency_ms = round((time.perf_counter() - started) * 1000, 2)

        cleaned = helper._clean_query(raw) if raw else ""
        safe = bool(cleaned) and helper._is_safe_query(cleaned)
        shape = bool(cleaned) and helper._matches_intent_shape(cleaned, intent)
        uses_node_schema = bool(cleaned) and ":NODE" in cleaned.upper()

        explain_ok = False
        explain_error = ""
        if cleaned and safe and shape:
            explain_ok, explain_error = _explain_parse(driver, cleaned)

        pass_all = bool(cleaned) and safe and shape and uses_node_schema and explain_ok

        rows.append(
            {
                "intent": intent,
                "user_input": user_input,
                "latency_ms": latency_ms,
                "raw": raw,
                "cleaned": cleaned,
                "safe": safe,
                "shape": shape,
                "uses_node_schema": uses_node_schema,
                "explain_ok": explain_ok,
                "pass_all": pass_all,
                "error": error,
                "explain_error": explain_error,
            }
        )

    summary = {
        "cases": len(rows),
        "pass_all": sum(1 for row in rows if row["pass_all"]),
        "safe_ok": sum(1 for row in rows if row["safe"]),
        "shape_ok": sum(1 for row in rows if row["shape"]),
        "schema_ok": sum(1 for row in rows if row["uses_node_schema"]),
        "parse_ok": sum(1 for row in rows if row["explain_ok"]),
        "avg_latency_ms": round(sum(row["latency_ms"] for row in rows) / max(1, len(rows)), 2),
    }

    return {"name": name, "summary": summary, "rows": rows}


def main() -> None:
    model_name = (LLM_MODEL_CYPHER or LLM_MODEL).strip()
    llm = LLMClient()
    helper = CypherGenerator()

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    try:
        results: List[Dict[str, Any]] = []
        for name, template in PROMPT_VARIANTS.items():
            print(f"Evaluating prompt variant: {name}")
            results.append(_evaluate_variant(name, template, llm, helper, driver, model_name))

        ranked = sorted(
            results,
            key=lambda item: (
                item["summary"]["pass_all"],
                item["summary"]["parse_ok"],
                item["summary"]["shape_ok"],
                item["summary"]["safe_ok"],
                -item["summary"]["avg_latency_ms"],
            ),
            reverse=True,
        )

        print("\nRanking:")
        for entry in ranked:
            summary = entry["summary"]
            print(
                "- "
                f"{entry['name']} | pass_all={summary['pass_all']}/{summary['cases']} "
                f"parse_ok={summary['parse_ok']} shape_ok={summary['shape_ok']} "
                f"safe_ok={summary['safe_ok']} avg_latency_ms={summary['avg_latency_ms']}"
            )

        winner = ranked[0]
        print(f"\nRecommended prompt variant: {winner['name']}")

        os.makedirs("logs", exist_ok=True)
        report_path = os.path.join("logs", "cypher_prompt_eval_latest.json")

        with open(report_path, "w", encoding="utf-8") as file:
            json.dump(
                {
                    "model_used": model_name,
                    "winner": winner["name"],
                    "results": results,
                },
                file,
                indent=2,
            )

        print(f"Detailed report written to: {report_path}")
    finally:
        driver.close()


if __name__ == "__main__":
    main()
