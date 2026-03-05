# Dual AI Chatbot Projects

Welcome to the **Dual AI Chatbot Projects** repository! This project demonstrates how Large Language Models (LLMs) can interact with different types of databases.

This repository contains two specialized AI chatbot agents, each designed for a different type of data retrieval and management.

---

## 🤖 The Agents

### 1. [Inventory Chatbot (SQL)](./inventory-chatbot)

A professional, terminal-based conversational agent that translates natural language into structured SQL queries.

- **Tech Stack**: Python, LangGraph, SQLite, SQL.
- **Use Case**: Querying and managing an enterprise relational database for inventory tracking. It handles intent recognition, SQL generation, automated error correction, and natural language synthesis.
- **Documentation**: [View SQL Chatbot Details](./inventory-chatbot/README.md)

### 2. [Knowledge Graph Chatbot (Neo4j)](./neo4j-chatbot)

An AI chatbot designed to interact with a highly connected Knowledge Graph representing Champions League Football data.

- **Tech Stack**: Python, Neo4j, Cypher Query Language.
- **Use Case**: Navigating complex relationships and connected data. It classifies intents (add, update, delete, inquire), dynamically generates Cypher queries, and executes them against a local Neo4j database.
- **Documentation**: [View Neo4j Chatbot Details](./neo4j-chatbot/README.md)

---

## 🚀 Getting Started

Each agent operates as an independent subsystem with its own environment, dependencies, and database.

To set up an agent, navigate to its respective directory and follow the instructions in its specific `README.md` file:

**For the SQL Inventory Database:**

```bash
cd inventory-chatbot
# Follow instructions in inventory-chatbot/README.md
```

**For the Neo4j Knowledge Graph:**

```bash
cd neo4j-chatbot
# Follow instructions in neo4j-chatbot/README.md
```

---

## 🧠 Supported LLM Providers

Both agents are built with clean architecture and support seamless switching between LLM providers via environment variables (`.env`).

- **Ollama**: For local, private, and free inference (e.g., `mistral`, `llama3`).
- **Groq**: For ultra-fast cloud inference.
- **OpenAI**: For state-of-the-art capability (`gpt-4o`).
