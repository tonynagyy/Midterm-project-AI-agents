import logging
import os
import re
import sqlite3
import threading
import time
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)


class LongMemoryStore:
    def __init__(
        self,
        enabled: bool,
        db_path: str,
        default_retrieve_items: int = 4,
        max_context_chars: int = 1200,
    ):
        self.enabled = enabled
        self.db_path = db_path
        self.default_retrieve_items = max(1, default_retrieve_items)
        self.max_context_chars = max(200, max_context_chars)

        self._conn = None
        self._lock = threading.Lock()

        if not self.enabled:
            logger.info("Long memory is disabled.")
            return

        if not self.db_path:
            self.db_path = "data/long_memory.sqlite"

        parent_dir = os.path.dirname(self.db_path)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)

        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row

        with self._conn:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS long_memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    thread_id TEXT NOT NULL,
                    user_text TEXT NOT NULL,
                    assistant_text TEXT NOT NULL,
                    intent TEXT,
                    created_at REAL NOT NULL
                )
                """
            )
            self._conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_long_memory_thread_created
                ON long_memory(thread_id, created_at DESC)
                """
            )

        logger.info("Long memory initialized at %s", self.db_path)

    @staticmethod
    def _extract_keywords(text: str) -> List[str]:
        tokens = re.findall(r"[a-zA-Z0-9]{3,}", (text or "").lower())
        unique = []
        seen = set()

        stop_words = {
            "the",
            "and",
            "for",
            "with",
            "that",
            "this",
            "from",
            "what",
            "where",
            "which",
            "who",
            "does",
            "play",
            "plays",
            "about",
            "tell",
            "show",
            "hello",
        }

        for token in tokens:
            if token in stop_words:
                continue
            if token in seen:
                continue
            seen.add(token)
            unique.append(token)
            if len(unique) >= 6:
                break

        return unique

    def add_turn(self, thread_id: str, user_text: str, assistant_text: str, intent: str = "") -> None:
        if not self.enabled or not self._conn:
            return

        thread = (thread_id or "default").strip()
        user = (user_text or "").strip()
        assistant = (assistant_text or "").strip()

        if not user and not assistant:
            return

        with self._lock:
            with self._conn:
                self._conn.execute(
                    """
                    INSERT INTO long_memory(thread_id, user_text, assistant_text, intent, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (thread, user[:1000], assistant[:1000], (intent or "").strip()[:40], time.time()),
                )

    def _query(self, thread_id: str, keywords: List[str], limit: int) -> List[Dict[str, str]]:
        if not self.enabled or not self._conn:
            return []

        base_query = (
            "SELECT id, thread_id, user_text, assistant_text, intent, created_at "
            "FROM long_memory WHERE thread_id = ?"
        )
        params: List[object] = [thread_id]

        if keywords:
            keyword_clauses = []
            for keyword in keywords:
                keyword_clauses.append("(lower(user_text) LIKE ? OR lower(assistant_text) LIKE ?)")
                like_value = f"%{keyword}%"
                params.extend([like_value, like_value])

            base_query += " AND (" + " OR ".join(keyword_clauses) + ")"

        base_query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with self._lock:
            rows = self._conn.execute(base_query, params).fetchall()

        return [dict(row) for row in rows]

    def peek(self, thread_id: str, limit: int = 10) -> List[Dict[str, str]]:
        thread = (thread_id or "default").strip()
        row_limit = max(1, limit)
        return self._query(thread, keywords=[], limit=row_limit)

    def build_context(self, thread_id: str, user_input: str, retrieve_items: int | None = None) -> Tuple[str, int]:
        if not self.enabled or not self._conn:
            return "", 0

        thread = (thread_id or "default").strip()
        limit = max(1, int(retrieve_items or self.default_retrieve_items))

        keywords = self._extract_keywords(user_input)
        rows = self._query(thread, keywords=keywords, limit=limit)

        if not rows:
            rows = self._query(thread, keywords=[], limit=limit)

        if not rows:
            return "", 0

        lines = []
        for idx, row in enumerate(rows, start=1):
            user_text = str(row.get("user_text") or "").strip()
            assistant_text = str(row.get("assistant_text") or "").strip()
            lines.append(f"Memory {idx} User: {user_text}")
            lines.append(f"Memory {idx} Assistant: {assistant_text}")

        context = "\n".join(lines).strip()

        if len(context) > self.max_context_chars:
            truncated = context[: self.max_context_chars]
            if "\n" in truncated:
                truncated = truncated.rsplit("\n", 1)[0]
            context = truncated.strip()

        return context, len(rows)

    def close(self) -> None:
        if not self._conn:
            return

        with self._lock:
            self._conn.close()
            self._conn = None
