import os
from dotenv import load_dotenv

load_dotenv()


def _as_bool(value: str, default: bool = False) -> bool:
	if value is None:
		return default
	return value.strip().lower() in {"1", "true", "yes", "on"}

# Neo4j Configuration
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

# LLM Configuration
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama")  # 'ollama', 'openai', 'groq', or 'lmstudio'
LLM_MODEL = os.getenv("LLM_MODEL", "mistral")
LLM_MODEL_CYPHER = os.getenv("LLM_MODEL_CYPHER", "").strip()
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.0"))
LLM_MAX_TOKENS_DEFAULT = int(os.getenv("LLM_MAX_TOKENS_DEFAULT", "120"))
LLM_MAX_TOKENS_CLASSIFIER = int(os.getenv("LLM_MAX_TOKENS_CLASSIFIER", "8"))
LLM_MAX_TOKENS_CYPHER = int(os.getenv("LLM_MAX_TOKENS_CYPHER", "80"))
LLM_MAX_TOKENS_RESPONSE = int(os.getenv("LLM_MAX_TOKENS_RESPONSE", "80"))
LLM_MAX_TOKENS_CHITCHAT = int(os.getenv("LLM_MAX_TOKENS_CHITCHAT", "60"))

# Provider Specifics

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
LMSTUDIO_URL = os.getenv("LMSTUDIO_URL", "http://localhost:1234/v1/chat/completions")

# Runtime, Observability, and Memory
SHORT_MEMORY_TURNS = int(os.getenv("SHORT_MEMORY_TURNS", "5"))
LONG_MEMORY_ENABLED = _as_bool(os.getenv("LONG_MEMORY_ENABLED", "true"))
LONG_MEMORY_DB_PATH = os.getenv("LONG_MEMORY_DB_PATH", "data/long_memory.sqlite")
LONG_MEMORY_RETRIEVE_ITEMS = int(os.getenv("LONG_MEMORY_RETRIEVE_ITEMS", "4"))
LONG_MEMORY_MAX_CONTEXT_CHARS = int(os.getenv("LONG_MEMORY_MAX_CONTEXT_CHARS", "1200"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = os.getenv("LOG_FILE", "logs/chatbot.log")

LANGSMITH_TRACING = _as_bool(os.getenv("LANGSMITH_TRACING", "false"))
LANGSMITH_API_KEY = os.getenv("LANGSMITH_API_KEY", "")
LANGSMITH_PROJECT = os.getenv("LANGSMITH_PROJECT", "neo4j-chatbot")
LANGSMITH_ENDPOINT = os.getenv("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com")


CLASSIFIER_PROMPT = """You are an intent classifier for a football knowledge graph chatbot.

Classify the user input into EXACTLY ONE of these intents:
- add       → User states a fact or provides new information. Examples: "Messi plays for Inter Miami", "Tony is from Spain", "Add that X plays for Y"
- inquire   → User asks a question about existing data. Examples: "Who does Messi play for?", "Where is Tony from?", "What team is X on?"
- update    → User wants to change an existing fact. Examples: "Update Messi's team to Barcelona", "Change X's club to Y"
- delete    → User wants to remove a fact or entity. Examples: "Delete Messi", "Remove the fact that X plays for Y"
- chitchat  → General conversation unrelated to data. Examples: "Hello", "Thanks", "How are you?"

RULES:
1. A plain declarative sentence stating a fact (e.g. "X plays for Y", "X is from Z") is ALWAYS "add".
2. Only use "inquire" when there is a clear question mark OR question words (who, what, where, which, does, is, are).
3. Respond with ONLY the single lowercase intent word. No punctuation, no explanation, no extra text.
4. Output budget is exactly one token from this set: add, inquire, update, delete, chitchat.

Recent Conversation (optional):
{memory_context}

Current User Input: {user_input}
Intent:"""


CYPHER_GENERATOR_PROMPT = """You are a text2cypher model.

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

Cypher:"""


RESPONSE_ENGINE_PROMPT = """You are a helpful football chatbot assistant. Translate the raw database results into a clear, concise, natural language response.

STRICT RULES:
- Use ONLY the information in Raw Data. Do NOT invent or assume any facts.
- If Raw Data is empty or "No results found.", say clearly that the information was not found.
- For add/update/delete operations, confirm the action was completed successfully.
- Keep the response to exactly 1 short sentence.
- Hard length cap: maximum 20 words.
- Do NOT list raw Cypher, JSON, or technical details.

User Input: {user_input}
Recent Conversation (optional):
{memory_context}

Operation: {action_msg}
Raw Data: {db_results}

Response:"""
