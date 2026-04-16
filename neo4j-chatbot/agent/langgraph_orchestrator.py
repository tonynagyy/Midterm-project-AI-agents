import logging
import os
import time
from typing import Any, Dict, List, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from config import (
    LANGSMITH_API_KEY,
    LANGSMITH_ENDPOINT,
    LANGSMITH_PROJECT,
    LANGSMITH_TRACING,
    LONG_MEMORY_DB_PATH,
    LONG_MEMORY_ENABLED,
    LONG_MEMORY_MAX_CONTEXT_CHARS,
    LONG_MEMORY_RETRIEVE_ITEMS,
    LLM_MODEL,
    LLM_PROVIDER,
    SHORT_MEMORY_TURNS,
)
from .classifier import IntentClassifier
from .cypher_generator import CypherGenerator
from .executor import Neo4jExecutor
from .long_memory import LongMemoryStore
from .response_engine import ResponseEngine

try:
    from langsmith import traceable
except Exception:  # pragma: no cover
    def traceable(*_args, **_kwargs):
        def _decorator(func):
            return func

        return _decorator


logger = logging.getLogger(__name__)

INTENT_ACTION_MAP = {
    "add": "Added",
    "update": "Updated",
    "delete": "Deleted",
    "inquire": "Queried",
}


class ChatState(TypedDict, total=False):
    thread_id: str
    user_input: str
    started_at: float
    memory_window: List[Dict[str, str]]
    short_memory_context: str
    long_memory_context: str
    long_memory_hits: int
    memory_context: str
    intent: str
    action_msg: str
    cypher_query: str
    raw_results: List[Dict[str, Any]]
    response: str
    error: str
    latency_ms: float
    metrics: Dict[str, Any]


class LangGraphOrchestrator:
    def __init__(self):
        self.short_memory_turns = max(0, SHORT_MEMORY_TURNS)
        self.classifier = IntentClassifier()
        self.generator = CypherGenerator()
        self.executor = Neo4jExecutor()
        self.responder = ResponseEngine()
        self.long_memory = LongMemoryStore(
            enabled=LONG_MEMORY_ENABLED,
            db_path=LONG_MEMORY_DB_PATH,
            default_retrieve_items=LONG_MEMORY_RETRIEVE_ITEMS,
            max_context_chars=LONG_MEMORY_MAX_CONTEXT_CHARS,
        )

        self._configure_langsmith()
        self._checkpointer = MemorySaver()
        self.graph = self._build_graph()

        logger.info(
            "LangGraph orchestrator initialized | provider=%s model=%s short_memory_turns=%s long_memory=%s",
            LLM_PROVIDER,
            LLM_MODEL,
            self.short_memory_turns,
            "enabled" if LONG_MEMORY_ENABLED else "disabled",
        )

    def _configure_langsmith(self) -> None:
        if not LANGSMITH_TRACING:
            logger.info("LangSmith tracing disabled.")
            return

        os.environ["LANGSMITH_TRACING"] = "true"

        if LANGSMITH_API_KEY:
            os.environ["LANGSMITH_API_KEY"] = LANGSMITH_API_KEY
        if LANGSMITH_PROJECT:
            os.environ["LANGSMITH_PROJECT"] = LANGSMITH_PROJECT
        if LANGSMITH_ENDPOINT:
            os.environ["LANGSMITH_ENDPOINT"] = LANGSMITH_ENDPOINT

        logger.info("LangSmith tracing enabled for project '%s'.", LANGSMITH_PROJECT)

    def _build_graph(self):
        builder = StateGraph(ChatState)

        builder.add_node("bootstrap", self._bootstrap)
        builder.add_node("prepare_memory", self._prepare_memory)
        builder.add_node("classify", self._classify_intent)
        builder.add_node("chitchat", self._handle_chitchat)
        builder.add_node("generate_cypher", self._generate_cypher)
        builder.add_node("execute_query", self._execute_query)
        builder.add_node("build_response", self._build_response)
        builder.add_node("finalize", self._finalize)

        builder.set_entry_point("bootstrap")
        builder.add_edge("bootstrap", "prepare_memory")
        builder.add_edge("prepare_memory", "classify")

        builder.add_conditional_edges(
            "classify",
            self._route_after_classify,
            {
                "chitchat": "chitchat",
                "db_path": "generate_cypher",
                "finalize": "finalize",
            },
        )

        builder.add_conditional_edges(
            "generate_cypher",
            self._route_after_error,
            {
                "continue": "execute_query",
                "finalize": "finalize",
            },
        )

        builder.add_conditional_edges(
            "execute_query",
            self._route_after_error,
            {
                "continue": "build_response",
                "finalize": "finalize",
            },
        )

        builder.add_edge("build_response", "finalize")
        builder.add_edge("chitchat", "finalize")
        builder.add_edge("finalize", END)

        return builder.compile(checkpointer=self._checkpointer)

    def _bootstrap(self, state: ChatState) -> Dict[str, Any]:
        return {
            "thread_id": state.get("thread_id", "default"),
            "started_at": time.time(),
            "error": "",
            "cypher_query": "",
            "raw_results": [],
            "response": "",
            "intent": "",
            "action_msg": "",
        }

    def _prepare_memory(self, state: ChatState) -> Dict[str, Any]:
        memory_window = list(state.get("memory_window") or [])
        if self.short_memory_turns:
            memory_window = memory_window[-self.short_memory_turns :]
        else:
            memory_window = []

        short_memory_context = self._format_memory(memory_window)

        thread_id = state.get("thread_id", "default")
        long_memory_context, long_memory_hits = self.long_memory.build_context(
            thread_id=thread_id,
            user_input=state.get("user_input", ""),
        )

        memory_context = self._compose_memory_context(
            short_memory_context=short_memory_context,
            long_memory_context=long_memory_context,
        )

        return {
            "memory_window": memory_window,
            "short_memory_context": short_memory_context,
            "long_memory_context": long_memory_context,
            "long_memory_hits": long_memory_hits,
            "memory_context": memory_context,
        }

    def _classify_intent(self, state: ChatState) -> Dict[str, Any]:
        user_input = state.get("user_input", "")
        memory_context = state.get("memory_context", "")

        try:
            intent = self.classifier.classify(
                user_input=user_input,
                memory_context=memory_context,
            )
            logger.info("Intent classified as '%s'.", intent)
            return {
                "intent": intent,
                "action_msg": INTENT_ACTION_MAP.get(intent, "Processed"),
            }
        except Exception as exc:
            logger.exception("Intent classification failed.")
            return {
                "error": str(exc),
                "intent": "inquire",
                "action_msg": "Processed",
            }

    def _route_after_classify(self, state: ChatState) -> str:
        if state.get("error"):
            return "finalize"
        if state.get("intent") == "chitchat":
            return "chitchat"
        return "db_path"

    def _generate_cypher(self, state: ChatState) -> Dict[str, Any]:
        try:
            cypher = self.generator.generate(
                user_input=state.get("user_input", ""),
                intent=state.get("intent", "inquire"),
                memory_context=state.get("memory_context", ""),
            )
            logger.debug("Generated Cypher query: %s", cypher)
            return {"cypher_query": cypher}
        except Exception as exc:
            logger.exception("Cypher generation failed.")
            return {"error": str(exc)}

    def _execute_query(self, state: ChatState) -> Dict[str, Any]:
        cypher_query = state.get("cypher_query", "")
        if not cypher_query:
            return {"error": "No Cypher query was generated."}

        try:
            raw_results = self.executor.execute_query(cypher_query)
            return {"raw_results": raw_results}
        except Exception as exc:
            logger.exception("Neo4j query execution failed.")
            return {"error": str(exc)}

    def _build_response(self, state: ChatState) -> Dict[str, Any]:
        try:
            response = self.responder.generate_response(
                user_input=state.get("user_input", ""),
                db_results=state.get("raw_results", []),
                action_msg=state.get("action_msg", "Processed"),
                intent=state.get("intent", "inquire"),
                memory_context=state.get("memory_context", ""),
            )
            return {"response": response}
        except Exception as exc:
            logger.exception("Response generation failed.")
            return {"error": str(exc)}

    def _handle_chitchat(self, state: ChatState) -> Dict[str, Any]:
        try:
            response = self.responder.generate_chitchat(
                user_input=state.get("user_input", ""),
                memory_context=state.get("memory_context", ""),
            )
            return {"response": response}
        except Exception as exc:
            logger.exception("Chitchat response failed.")
            return {"error": str(exc)}

    def _route_after_error(self, state: ChatState) -> str:
        if state.get("error"):
            return "finalize"
        return "continue"

    def _finalize(self, state: ChatState) -> Dict[str, Any]:
        response = state.get("response", "").strip()
        if not response:
            if state.get("error"):
                response = f"I'm sorry, I encountered an error: {state.get('error')}"
            else:
                response = "I could not process that request. Please try again."

        latency_ms = round((time.time() - state.get("started_at", time.time())) * 1000, 2)

        memory_window = list(state.get("memory_window") or [])
        memory_window.append(
            {
                "user": state.get("user_input", ""),
                "assistant": response,
            }
        )
        if self.short_memory_turns:
            memory_window = memory_window[-self.short_memory_turns :]
        else:
            memory_window = []

        self.long_memory.add_turn(
            thread_id=state.get("thread_id", "default"),
            user_text=state.get("user_input", ""),
            assistant_text=response,
            intent=state.get("intent", ""),
        )

        metrics = {
            "latency_ms": latency_ms,
            "intent": state.get("intent", "unknown"),
            "rows_returned": len(state.get("raw_results") or []),
            "had_error": bool(state.get("error")),
            "memory_turns": len(memory_window),
            "long_memory_hits": int(state.get("long_memory_hits") or 0),
        }

        logger.info(
            "Turn completed | intent=%s latency_ms=%s rows=%s had_error=%s memory_turns=%s",
            metrics["intent"],
            metrics["latency_ms"],
            metrics["rows_returned"],
            metrics["had_error"],
            metrics["memory_turns"],
        )

        return {
            "response": response,
            "latency_ms": latency_ms,
            "metrics": metrics,
            "memory_window": memory_window,
        }

    @staticmethod
    def _compose_memory_context(short_memory_context: str, long_memory_context: str) -> str:
        parts = []
        if short_memory_context:
            parts.append("Short Memory:\n" + short_memory_context)
        if long_memory_context:
            parts.append("Long Memory:\n" + long_memory_context)
        return "\n\n".join(parts)

    @staticmethod
    def _format_memory(memory_window: List[Dict[str, str]]) -> str:
        if not memory_window:
            return ""

        lines = []
        for index, turn in enumerate(memory_window, start=1):
            user_text = turn.get("user", "").strip()
            assistant_text = turn.get("assistant", "").strip()
            lines.append(f"Turn {index} User: {user_text}")
            lines.append(f"Turn {index} Assistant: {assistant_text}")

        return "\n".join(lines)

    @traceable(name="langgraph_chat_turn", run_type="chain")
    def run_turn(self, user_input: str, thread_id: str = "default") -> Dict[str, Any]:
        run_config = {
            "configurable": {"thread_id": thread_id},
            "tags": ["langgraph", "neo4j-chatbot"],
            "metadata": {
                "llm_provider": LLM_PROVIDER,
                "llm_model": LLM_MODEL,
                "short_memory_turns": self.short_memory_turns,
            },
        }

        state = self.graph.invoke(
            {
                "user_input": user_input,
                "thread_id": thread_id,
            },
            config=run_config,
        )

        return {
            "response": state.get("response", ""),
            "intent": state.get("intent", "unknown"),
            "cypher_query": state.get("cypher_query", ""),
            "raw_results": state.get("raw_results", []),
            "error": state.get("error", ""),
            "latency_ms": state.get("latency_ms", 0.0),
            "metrics": state.get("metrics", {}),
            "memory_turns": len(state.get("memory_window") or []),
            "long_memory_hits": int(state.get("long_memory_hits") or 0),
        }

    def peek_long_memory(self, thread_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        return self.long_memory.peek(thread_id=thread_id, limit=limit)

    def close(self) -> None:
        self.long_memory.close()
        self.executor.close()
