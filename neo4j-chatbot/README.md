# Neo4j AI Chatbot (Champions League Football)

An AI chatbot that uses a LangGraph workflow to answer questions and interact with a Champions League Football Knowledge Graph stored in Neo4j.

The runtime now includes:

- LangGraph state-machine orchestration
- Optional LangSmith tracing/metrics
- Centralized logging to console and file
- Short-term conversation memory (rolling window)
- Long-term persistent memory (SQLite-backed)

## Prerequisites & Setup

### 1. Python Virtual Environment

First, ensure you have Python 3.9+ installed. Create a virtual environment:

```bash
python -m venv venv
```

### 2. Activate Virtual Environment

**Windows:**

```bash
venv\Scripts\activate
```

**macOS/Linux:**

```bash
source venv/bin/activate
```

### 3. Install Dependencies

Install the required packages using `requirements.txt`:

```bash
pip install -r requirements.txt
```

### 4. Environment Configuration (.env)

Copy the example environment file and configure your settings:

```bash
cp .env.example .env
```

Open `.env` and configure the variables based on your preferred LLM provider:

| Provider      | `LLM_PROVIDER` | Extra Variable(s) | Notes                            |
| :------------ | :------------- | :---------------- | :------------------------------- |
| **Ollama**    | `ollama`       | `OLLAMA_URL`      | Local, free, offline             |
| **OpenAI**    | `openai`       | `OPENAI_API_KEY`  | High quality, paid               |
| **Groq**      | `groq`         | `GROQ_API_KEY`    | Extremely fast, free tier        |
| **LM Studio** | `lmstudio`     | `LMSTUDIO_URL`    | Local OpenAI-compatible endpoint |

LangGraph / Observability / Memory settings:

- `SHORT_MEMORY_TURNS` (default `5`): Rolling number of user-assistant turns kept per session.
- `LONG_MEMORY_ENABLED` (default `true`): Enables persistent long memory.
- `LONG_MEMORY_DB_PATH` (default `data/long_memory.sqlite`): SQLite path for long-memory storage.
- `LONG_MEMORY_RETRIEVE_ITEMS` (default `4`): Number of long-memory entries to retrieve for context.
- `LONG_MEMORY_MAX_CONTEXT_CHARS` (default `1200`): Max characters injected from long memory into prompt context.
- `LOG_LEVEL` (default `INFO`): Logger level.
- `LOG_FILE` (default `logs/chatbot.log`): File path for rotating logs.
- `LANGSMITH_TRACING` (`true`/`false`): Enables LangSmith tracing.
- `LANGSMITH_API_KEY`: Required when tracing is enabled.
- `LANGSMITH_PROJECT`: LangSmith project name.
- `LANGSMITH_ENDPOINT`: LangSmith API endpoint.

LLM output budget settings:

- `LLM_MAX_TOKENS_DEFAULT` (default `120`): Fallback max output tokens for uncategorized LLM calls.
- `LLM_MAX_TOKENS_CLASSIFIER` (default `8`): Token cap for intent classification.
- `LLM_MAX_TOKENS_CYPHER` (default `80`): Token cap for Cypher generation.
- `LLM_MAX_TOKENS_RESPONSE` (default `80`): Token cap for response wording.
- `LLM_MAX_TOKENS_CHITCHAT` (default `60`): Token cap for casual conversation replies.

Optional task-specific model override:

- `LLM_MODEL_CYPHER` (default empty): If set, only Cypher generation uses this model while other tasks still use `LLM_MODEL`.
- Example: `LLM_MODEL_CYPHER=qwen2-5-coder-0-5b-neo4j-text2cypher-2024v1`
- Practical baseline for first-time use of `qwen2-5-coder-0-5b-neo4j-text2cypher-2024v1`: keep `LLM_MAX_TOKENS_CYPHER=80` and use the compact Cypher prompt in `config.py`.

---

## Subsystem Setup

### 1. LLM Provider Setup

#### **Option A: Ollama (Local)**

1. Download from [ollama.com](https://ollama.com/download).
2. Install and run the application.
3. Pull the model:
   ```bash
   ollama run mistral
   ```
4. Set `.env`: `LLM_PROVIDER=ollama`, `LLM_MODEL=mistral`.

#### **Option B: Groq (Cloud)**

1. Get a free API key at [groq.com](https://groq.com/).
2. Set `.env`: `LLM_PROVIDER=groq`, `GROQ_API_KEY=gsk_...`
3. Suggested Model: `llama-3.3-70b-versatile` or `llama-3.1-8b-instant`.

#### **Option C: OpenAI (Cloud)**

1. Get an API key from [platform.openai.com](https://platform.openai.com/).
2. Set `.env`: `LLM_PROVIDER=openai`, `OPENAI_API_KEY=sk-...`
3. Suggested Model: `gpt-4o` or `gpt-3.5-turbo`.

---

### 2. Neo4j Database Setup

1. **Download Neo4j Desktop**: [neo4j.com/download](https://neo4j.com/download/).
2. **Create a Local DBMS**:
   - Open Neo4j Desktop and create a new project.
   - Click **Add** -> **Local DBMS**.
   - Set the name (e.g., "Football-Graph") and password (default is `password`).
3. **Start the DBMS**: Click the **Start** button.
4. **Connection Check**: Ensure it is reachable at `bolt://localhost:7687`.
5. **Update .env**: Ensure `NEO4J_PASSWORD` matches what you set.

### 3. Viewing the Database Visually (Neo4j Browser)

To view the graph and verify your data visually as nodes and edges:

1. Open your web browser and navigate to **http://localhost:7474**.
2. Log in using the credentials from your `.env` file (by default, Username: `neo4j`, Password: `<your_password>`).
3. In the query bar at the top, enter the following Cypher query and press Enter (or click Play) to view all nodes and connections:
   ```cypher
   MATCH (n) RETURN n
   ```
4. You can click on individual nodes to explore their properties (e.g., names, stats) or test more specific Cypher queries, such as seeing who plays for Real Madrid:
   ```cypher
   MATCH (p:Person)-[r:PLAYS_FOR]->(t:Team {name: "Real Madrid"}) RETURN p, r, t
   ```

### 4. Run the Seed Loader

With Neo4j running, populate the knowledge graph with initial facts:

```bash
python seed_loader.py
```

This will insert 50 lines of Champions League football facts into Neo4j.

### 5. Run the Chatbot

Start the interactive terminal application:

```bash
python main.py
```

Start the Streamlit web app:

```bash
streamlit run app.py
```

Run the HTTP API server:

```bash
uvicorn api:app --host 0.0.0.0 --port 8000
```

Example API calls:

```bash
curl -X POST "http://localhost:8000/agent/chat" \
   -H "Content-Type: application/json" \
   -d '{"message":"who plays for arsenal?","thread_id":"api-demo"}'

curl "http://localhost:8000/agent/memory/api-demo?limit=5"
```

Run API tests:

```bash
python -m unittest discover -s tests -p "test_api.py"
```

## Runtime Behavior

- Every user turn runs through a LangGraph pipeline.
- A per-session thread ID is used to maintain short-term and long-term memory.
  - CLI uses `terminal-session`.
  - Streamlit uses a generated session UUID.
- Short memory is a rolling window limited by `SHORT_MEMORY_TURNS`.
- Long memory is persisted to SQLite and survives restarts when `LONG_MEMORY_ENABLED=true`.
- `add`, `update`, and `delete` intents use deterministic Cypher templates (no LLM fallback) for predictable write operations.
- `inquire` intent uses the Cypher model with an automatic EXPLAIN-driven cleanup/repair pass; if retries still fail, a deterministic inquire fallback query is used.
- Logs are written to both console and `LOG_FILE`.
- When `LANGSMITH_TRACING=true`, runs and node-level execution traces are sent to LangSmith.

### Viewing Memory

- CLI: type `/memory` to print the latest long-memory entries for `terminal-session`.
- Streamlit: enable Debug Mode and click `Show Long Memory Snapshot` in the sidebar.

## Example Interactions

**Inquire:**

> User: Who does Lionel Messi play for?
> Bot: Based on the knowledge graph, Lionel Messi plays for Inter Miami.

**Add:**

> User: Add the fact that Cody Gakpo plays for Liverpool.
> Bot: Successfully executed Cypher query. Fact added.

**Update:**

> User: Update the fact that Kylian Mbappé plays for Real Madrid to Paris Saint-Germain.
> Bot: Successfully executed Cypher query. Fact updated.

**Delete:**

> User: Remove the fact that Kevin De Bruyne plays for Manchester City.
> Bot: Successfully executed Cypher query. Fact removed.

**Chitchat:**

> User: Hello!
> Bot: Hello! How can I help you with Champions League football knowledge today?
