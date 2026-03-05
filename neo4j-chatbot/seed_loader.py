import os
import logging
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)
logging.getLogger("neo4j").setLevel(logging.WARNING)

#from agent.classifier import IntentClassifier
from agent.cypher_generator import CypherGenerator
from agent.executor import Neo4jExecutor


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
                # Force intent to 'add' — seed data is always additive
                cypher_query = generator.generate(line, "add")
                executor.execute_query(cypher_query)
                print("  ✓ Inserted\n")
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
