# Architecture Diagrams

## Inventory Chatbot (SQL) - System Flow

```mermaid
graph TD
    A[User Input] --> B[Router Node]
    B -- "Intent: Chat" --> C[Chat Node]
    B -- "Intent: SQL" --> D[SQL Generator Node]
    C --> E[Final Response]
    D --> F[SQL Executor Node]
    F -- "Success" --> G[Responder Node]
    F -- "Error" --> H[SQL Corrector Node]
    H --> F
    G --> E
```

## Inventory Chatbot (SQL) - Data Architecture

- **Engine**: LangGraph (State Machine)
- **Database**: SQLite3
- **LLM**: Mistral (via Ollama) / OpenAI
- **Filtering Logic**:
  - Default: `IsActive = 1` for dimension tables.
  - Default: Exclude `Status IN ('Disposed', 'Retired')` for Assets.

```

```
