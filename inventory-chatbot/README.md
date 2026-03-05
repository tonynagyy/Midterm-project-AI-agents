# Inventory Chatbot (SQL)

A professional AI terminal-based conversational agent that translates natural language into structured SQL queries to query an enterprise relational database.

## 🏗️ System Architecture

The chatbot operates as a state-machine based conversational agent using **LangGraph**. It handles intent recognition, SQL generation, automated error correction, and natural language synthesis.

(Detailed diagram available in [architecture.md](./architecture.md))

## 🚀 Setup & Installation

### 1. Prerequisites

- Python 3.10+
- **Ollama** (for local Mistral), **Groq**, or **OpenAI API Key**.

### 2. Environment Setup

1. Create and activate a virtual environment:
   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```
2. Install dependencies:
   ```powershell
   pip install -r requirements.txt
   ```

### 3. Database Initialization

Initialize and seed the local SQLite database from the provided schema and sample data:

```powershell
python setup_database.py
```

### 4. Configuration (.env)

Create a `.env` file in the root directory:

```env
# PROVIDER: 'ollama', 'groq', or 'openai'
PROVIDER=ollama
MODEL_NAME=mistral

# If using Groq or OpenAI
# GROQ_API_KEY=your_key
# OPENAI_API_KEY=your_key
```

## 🏃 Running the Application (CLI)

To launch the interactive terminal chatbot:

```powershell
python main.py
```

## 🛠️ Project Structure

- `main.py`: **Primary Entry Point** for terminal-based interaction.
- `agent/`: Core logic (Graph, Nodes, Prompts, State).
- `architecture.md`: Visual architecture diagrams.
- `inventory_chatbot.db`: Local SQLite database.
- `setup_database.py`: Database initialization script.
- `requirements.txt`: Project dependencies.
