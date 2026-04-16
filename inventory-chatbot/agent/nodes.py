import sqlite3
import re
import os
import time
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from .state import AgentState
from .prompts import ROUTER_PROMPT, SYSTEM_PROMPT, CHAT_PROMPT, RESPONSE_PROMPT, REPLAN_PROMPT, get_schema_string

def get_recent_messages(messages, k=5):
    """Return up to the last K messages, ignoring system messages."""
    return messages[-k:] if len(messages) > k else messages


def is_hallucination(text: str) -> bool:
    """Detects common math-problem hallucination patterns."""
    patterns = [
        r"Let [a-z]\([a-z]\) =", 
        r"Solve (for )?[a-z]",
        r"Suppose -?[a-z]+[+-]",
        r"Answer: \d+",
        r"y\(q\) =",
        r"w\(q\) =",
        r"floor\("
    ]
    for p in patterns:
        if re.search(p, text, re.IGNORECASE):
            return True
    return False

load_dotenv()

# Setup model based on .env
PROVIDER = os.getenv("PROVIDER", "ollama").lower()
MODEL_NAME = os.getenv("MODEL_NAME", "mistral")
DB_PATH = 'inventory_chatbot.db'

if PROVIDER == "openai":
    llm = ChatOpenAI(model=MODEL_NAME, temperature=0)
elif PROVIDER == "groq":
    llm = ChatGroq(model=MODEL_NAME, temperature=0)
else:
    llm = ChatOllama(model=MODEL_NAME, temperature=0)

def extract_sql(text: str) -> str:
    """Extracts raw SQL from LLM response by stripping markdown and chat text."""
    # 0. Check for hallucinations
    if is_hallucination(text):
        return "-- ERROR: Hallucination detected"
    # 1. Try markdown blocks first
    match = re.search(r'```(?:sql)?\n?(.*?)\n?```', text, re.DOTALL | re.IGNORECASE)
    if match: return match.group(1).strip()
    
    # 2. Match from first SQL keyword to semicolon or chatty ending
    sql_keywords = r'(SELECT|WITH|INSERT|UPDATE|DELETE|CREATE|DROP)'
    match = re.search(rf'\b{sql_keywords}\b', text, re.IGNORECASE)
    if match:
        sql_part = text[match.start():].strip()
        end_match = re.search(r';', sql_part)
        if end_match: return sql_part[:end_match.end()].strip()
            
        # 3. Strip common AI conversational suffixes if no semicolon
        lines = sql_part.split('\n')
        clean_lines = []
        for line in lines:
            if re.match(r'^(This|I hope|Let me|Note|You can)', line.strip(), re.IGNORECASE): break
            clean_lines.append(line)
        return '\n'.join(clean_lines).strip()
    return text.strip()

def router_node(state: AgentState):
    """Classifies user intent as 'sql' or 'chat'."""
    print("\n--- [NODE: ROUTER] ---")
    start_time = time.time()
    recent_history = get_recent_messages(state['messages'], k=5)
    messages = [SystemMessage(content=ROUTER_PROMPT)] + recent_history
    response = llm.invoke(messages)
    content = response.content.strip().lower()
    intent = 'sql' if 'sql' in content else 'chat'
    print(f"Detected Intent: {intent}")
    
    res = {"intent": intent, "latency_ms": int((time.time() - start_time) * 1000)}
    if intent == 'chat': res.update({"sql_query": None, "sql_result": None, "error": None})
    return res

def chat_node(state: AgentState):
    """Handles general conversation/greetings."""
    print("--- [NODE: CHAT] ---")
    start_time = time.time()
    recent_history = get_recent_messages(state['messages'], k=5)
    messages = [SystemMessage(content=CHAT_PROMPT)] + recent_history
    response = llm.invoke(messages)
    return {"messages": [response], "latency_ms": int((time.time() - start_time) * 1000)}

def sql_generator_node(state: AgentState):
    """Generates SQLite query from natural language."""
    print("--- [NODE: SQL GENERATOR] ---")
    start_time = time.time()
    schema = get_schema_string(DB_PATH)
    recent_history = get_recent_messages(state['messages'], k=5)
    messages = [SystemMessage(content=SYSTEM_PROMPT.format(schema=schema))] + recent_history
    response = llm.invoke(messages)
    sql_query = extract_sql(response.content)
    print(f"Generated SQL: {sql_query}")
    return {"sql_query": sql_query, "revision_count": 0, "latency_ms": int((time.time() - start_time) * 1000)}

def sql_executor_node(state: AgentState):
    """Executes SQL against local SQLite database."""
    print("--- [NODE: SQL EXECUTOR] ---")
    start_time = time.time()
    sql_query = state['sql_query']
    print(f"Executing: {sql_query}")
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(sql_query)
        rows = cursor.fetchall()
        result = [dict(row) for row in rows]
        conn.close()
        print(f"Success. Rows found: {len(result)}")
        return {"sql_result": result, "error": None, "latency_ms": int((time.time() - start_time) * 1000)}
    except Exception as e:
        print(f"Failed: {str(e)}")
        updates = {"error": str(e), "latency_ms": int((time.time() - start_time) * 1000)}
        if state.get("revision_count", 0) == 0:
            updates.update({"first_failing_query": sql_query, "first_error": str(e)})
        return updates

def sql_corrector_node(state: AgentState):
    """Fixes SQL syntax or logic errors."""
    print("--- [NODE: SQL CORRECTOR] ---")
    start_time = time.time()
    schema = get_schema_string(DB_PATH)
    p = REPLAN_PROMPT.format(error=state['error'], question=state['question'], sql_query=state['sql_query'], schema=schema)
    response = llm.invoke([SystemMessage(content=p)])
    sql_query = extract_sql(response.content)
    
    # If the LLM returns prose or non-supported functions instead of SQL, force a loop break.
    if any(k in sql_query for k in ["Question:", "Let ", "Solve ", "Answer:", "I apologize", "floor("]):
        print("Hallucination detected. Breaking loop.")
        return {
            "revision_count": 4, # Force termination in should_continue
            "error": "The system was unable to generate a valid database query.",
            "latency_ms": int((time.time() - start_time) * 1000)
        }
        
    print(f"Corrected SQL: {sql_query}")
    return {"sql_query": sql_query, "revision_count": state['revision_count'] + 1, "latency_ms": int((time.time() - start_time) * 1000)}

def responder_node(state: AgentState):
    """Produces the final natural language answer."""
    print("--- [NODE: RESPONDER] ---")
    start_time = time.time()
    
    if state.get('intent') == 'chat':
        return {"latency_ms": int((time.time() - start_time) * 1000)}

    # If we reached here with an error after all retries
    if state.get('error'):
         error_content = f"I'm sorry, I encountered an issue accessing the inventory data: {state['error']}"
         return {
             "messages": [AIMessage(content=error_content)],
             "latency_ms": int((time.time() - start_time) * 1000)
         }

    data = state.get('sql_result', [])
    formatted_data = str(data) if data else "No records found."

    prompt = RESPONSE_PROMPT.format(
        sql_query=state['sql_query'],
        sql_result=formatted_data
    )
    
    # Use HumanMessage for better adherence to the reporting template
    response = llm.invoke([HumanMessage(content=prompt)])
    content = response.content.strip()

    # Robust marker stripping using regex (case-insensitive)
    content = re.sub(r'\[\s*REPORT\s+START\s*\]', '', content, flags=re.IGNORECASE)
    content = re.sub(r'\[\s*REPORT\s+END\s*\]', '', content, flags=re.IGNORECASE)
    content = re.sub(r'#+\s*REPORT\s+(START|END)\s*#*', '', content, flags=re.IGNORECASE)
    content = content.strip()

    # --- HALLUCINATION FALLBACK ---
    if is_hallucination(content):
        print("!!! RESPONDER HALLUCINATION DETECTED. Using fallback summary !!!")
        if not data or data == "No records found.":
            content = "No relevant records were found in the database."
        else:
            # Generate a professional, deterministic summary of the data lists
            summary_parts = []
            if isinstance(data, list) and len(data) > 0:
                summary_parts.append(f"Found {len(data)} results:")
                # List the first 5 items to keep it concise
                for item in data[:5]:
                    summary_parts.append(f"- {str(item)}")
                if len(data) > 5:
                    summary_parts.append(f"... and {len(data)-5} more.")
            else:
                summary_parts.append(f"Result: {str(data)}")
            content = "\n".join(summary_parts)
    
    # Always create a new AIMessage with the cleaned content
    response = AIMessage(content=content)

    return {
        "messages": [response],
        "latency_ms": state.get("latency_ms", 0) + int((time.time() - start_time) * 1000)
    }
