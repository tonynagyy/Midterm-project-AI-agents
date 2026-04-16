import os
import logging
import re
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)
logging.getLogger("neo4j").setLevel(logging.WARNING)

#from agent.classifier import IntentClassifier
from agent.cypher_generator import CypherGenerator
from agent.executor import Neo4jExecutor


def _escape_cypher_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def _build_fallback_add_query(fact_line: str) -> str | None:
    """Create a deterministic ADD query for known seed-data sentence patterns."""
    sentence = fact_line.strip()

    patterns = [
        (r"^(?P<subject>.+?) plays for (?P<object>.+?)\.?$", "PLAYS_FOR"),
        (r"^(?P<subject>.+?) is from (?P<object>.+?)\.?$", "IS_FROM"),
        (r"^(?P<subject>.+?) played in the (?P<object>.+?)\.?$", "PLAYED_IN"),
    ]

    for pattern, relation in patterns:
        match = re.match(pattern, sentence)
        if not match:
            continue

        subject = _escape_cypher_string(match.group("subject").strip())
        obj = _escape_cypher_string(match.group("object").strip())

        return (
            f"MERGE (a:Node {{name: '{subject}'}})\n"
            f"MERGE (b:Node {{name: '{obj}'}})\n"
            f"MERGE (a)-[:{relation}]->(b)"
        )

    return None


def load_seed_data(file_path: str = "seed_data.txt"):
    if not os.path.exists(file_path):
        print(f"Error: '{file_path}' not found.")
        return

    #classifier = IntentClassifier()
    generator = CypherGenerator()
    executor = Neo4jExecutor()

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]

        print(f"Seeding {len(lines)} facts into Neo4j...\n" + "-" * 45)
        success, failed = 0, 0

        for i, line in enumerate(lines, 1):
            print(f"[{i}/{len(lines)}] {line}")
            try:
                fallback_query = _build_fallback_add_query(line)

                if fallback_query:
                    executor.execute_query(fallback_query)
                    print("  ✓ Inserted\n")
                    success += 1
                    continue

                # Unknown sentence pattern: use LLM add generation as fallback.
                cypher_query = generator.generate(line, "add")
                executor.execute_query(cypher_query)
                print("  ✓ Inserted (llm query)\n")
                success += 1
            except Exception as e:
                print(f"  ✗ Failed: {e}\n")
                failed += 1

        print("-" * 45)
        print(f"Seed complete. Success: {success} | Failed: {failed}")

    finally:
        executor.close()


if __name__ == "__main__":
    load_seed_data()
