import logging
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)
logging.getLogger("neo4j").setLevel(logging.WARNING)

import sys
from agent.classifier import IntentClassifier
from agent.cypher_generator import CypherGenerator
from agent.executor import Neo4jExecutor
from agent.response_engine import ResponseEngine

logging.getLogger("config").setLevel(logging.WARNING)
logging.getLogger("agent.executor").setLevel(logging.WARNING)
logging.getLogger("agent.classifier").setLevel(logging.WARNING)
logging.getLogger("agent.cypher_generator").setLevel(logging.WARNING)
logging.getLogger("agent.response_engine").setLevel(logging.WARNING)

# Map intents to human-readable action labels for the response engine
INTENT_ACTION_MAP = {
    "add": "Added",
    "update": "Updated",
    "delete": "Deleted",
    "inquire": "Queried",
}


class ChatbotOrchestrator:
    def __init__(self):
        print("Initializing models and database connection...")
        try:
            self.classifier = IntentClassifier()
            self.generator = CypherGenerator()
            self.executor = Neo4jExecutor()
            self.responder = ResponseEngine()
            self.memory = []

            from config import LLM_PROVIDER, LLM_MODEL
            print(f"Provider : {LLM_PROVIDER}")
            print(f"Model    : {LLM_MODEL}")
            print("\n" + "=" * 55)
            print("  Welcome to the Champions League Knowledge Graph Bot")
            print("  Type 'exit' or 'quit' to close.")
            print("=" * 55 + "\n")
        except Exception as e:
            print(f"\nFatal error during initialization: {e}")
            sys.exit(1)

    def process_input(self, user_input: str):
        try:
            # Step 1 – classify intent
            intent = self.classifier.classify(user_input)
            logger = logging.getLogger(__name__)
            logger.info(f"Intent: {intent}")

            # Step 2 – handle chitchat without hitting the DB
            if intent == "chitchat":
                response = self.responder.generate_chitchat(user_input)
                print(f"\nBot: {response}\n")
                return

            # Step 3 – generate Cypher query
            cypher_query = self.generator.generate(user_input, intent)

            # Step 4 – execute against Neo4j
            raw_results = self.executor.execute_query(cypher_query)

            # Step 5 – convert to natural language
            action_msg = INTENT_ACTION_MAP.get(intent, "Processed")
            response = self.responder.generate_response(
                user_input, raw_results, action_msg, intent
            )
            print(f"\nBot: {response}\n")

            # Keep a short rolling memory (for context display only)
            self.memory.append(user_input)
            if len(self.memory) > 5:
                self.memory.pop(0)

        except ValueError as e:
            # Cypher generation failed after retries
            print(f"\nBot: I couldn't generate a valid query for that request. Please try rephrasing.\nDetail: {e}\n")
        except Exception as e:
            print(f"\nBot: I'm sorry, I encountered an error: {e}\n")

    def run(self):
        while True:
            try:
                user_input = input("You: ").strip()
                if not user_input:
                    continue
                if user_input.lower() in {"exit", "quit", "q"}:
                    print("Goodbye!")
                    break
                self.process_input(user_input)
            except KeyboardInterrupt:
                print("\nGoodbye!")
                break
            except Exception as e:
                print(f"\nUnexpected error: {e}")

        self.executor.close()


if __name__ == "__main__":
    app = ChatbotOrchestrator()
    app.run()
