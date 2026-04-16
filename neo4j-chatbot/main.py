import logging
import sys

from agent.langgraph_orchestrator import LangGraphOrchestrator
from agent.logging_setup import setup_logging
from config import LLM_MODEL, LLM_PROVIDER, LONG_MEMORY_ENABLED, SHORT_MEMORY_TURNS

setup_logging()
logger = logging.getLogger(__name__)


class ChatbotCLI:
    def __init__(self):
        print("Initializing LangGraph chatbot and database connection...")
        try:
            self.orchestrator = LangGraphOrchestrator()

            print(f"Provider : {LLM_PROVIDER}")
            print(f"Model    : {LLM_MODEL}")
            print(f"Short Memory Turns : {SHORT_MEMORY_TURNS}")
            print(f"Long Memory        : {'enabled' if LONG_MEMORY_ENABLED else 'disabled'}")
            print("\n" + "=" * 55)
            print("  Welcome to the Champions League Knowledge Graph Bot")
            print("  Runtime: LangGraph + LangSmith tracing (optional)")
            print("  Type 'exit' or 'quit' to close.")
            print("  Type '/memory' to view saved long-memory entries.")
            print("  Supported LLM providers: ollama, openai, groq, lmstudio")
            print("=" * 55 + "\n")
        except Exception as exc:
            logger.exception("Fatal startup error.")
            print(f"\nFatal error during initialization: {exc}")
            sys.exit(1)

    def process_input(self, user_input: str):
        result = self.orchestrator.run_turn(
            user_input=user_input,
            thread_id="terminal-session",
        )
        print(f"\nBot: {result['response']}\n")

    def show_long_memory(self):
        rows = self.orchestrator.peek_long_memory(thread_id="terminal-session", limit=10)
        if not rows:
            print("\nLong Memory: no saved entries yet.\n")
            return

        print("\nLong Memory (latest 10):")
        for idx, row in enumerate(rows, start=1):
            intent = str(row.get("intent") or "unknown")
            user_text = str(row.get("user_text") or "").strip()
            assistant_text = str(row.get("assistant_text") or "").strip()
            print(f"{idx}. [{intent}] User: {user_text}")
            print(f"   Assistant: {assistant_text}")
        print("")

    def run(self):
        try:
            while True:
                user_input = input("You: ").strip()
                if not user_input:
                    continue
                if user_input.lower() in {"exit", "quit", "q"}:
                    print("Goodbye!")
                    break
                if user_input.lower() in {"/memory", "memory"}:
                    self.show_long_memory()
                    continue

                try:
                    self.process_input(user_input)
                except Exception as exc:
                    logger.exception("Failed to process input.")
                    print(f"\nBot: I'm sorry, I encountered an error: {exc}\n")
        except KeyboardInterrupt:
            print("\nGoodbye!")
        finally:
            self.orchestrator.close()


if __name__ == "__main__":
    app = ChatbotCLI()
    app.run()
