import sqlite3
import re
import os
import time
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from .state import AgentState
from .prompts import ROUTER_PROMPT, SYSTEM_PROMPT, CHAT_PROMPT, RESPONSE_PROMPT, REPLAN_PROMPT, get_schema_string

load_dotenv()

# Setup model based on .env
PROVIDER = os.getenv("PROVIDER", "ollama").lower()
MODEL_NAME = os.getenv("MODEL_NAME", "mistral")
DB_PATH = 'inventory_chatbot.db'

if PROVIDER == "openai":
    llm = ChatOpenAI(model=MODEL_NAME, temperature=0)
else:
    llm = ChatOllama(model=MODEL_NAME, temperature=0)

def extract_sql(text: str) -> str:
    """Extracts raw SQL from LLM response by stripping markdown and chat text."""
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
    messages = [SystemMessage(content=ROUTER_PROMPT), HumanMessage(content=state['question'])]
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
    messages = [SystemMessage(content=CHAT_PROMPT), HumanMessage(content=state['question'])]
    response = llm.invoke(messages)
    return {"messages": [response], "latency_ms": int((time.time() - start_time) * 1000)}

def sql_generator_node(state: AgentState):
    """Generates SQLite query from natural language."""
    print("--- [NODE: SQL GENERATOR] ---")
    start_time = time.time()
    schema = get_schema_string(DB_PATH)
    messages = [SystemMessage(content=SYSTEM_PROMPT.format(schema=schema)), HumanMessage(content=state['question'])]
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
    
    if any(k in sql_query for k in ["Question:", "Let ", "Solve ", "Answer:"]):
        print("Hallucination detected. Halting loop.")
        return {"revision_count": state['revision_count'] + 1, "latency_ms": int((time.time() - start_time) * 1000)}
        
    print(f"Corrected SQL: {sql_query}")
    return {"sql_query": sql_query, "revision_count": state['revision_count'] + 1, "latency_ms": int((time.time() - start_time) * 1000)}

def responder_node(state: AgentState):
    """Produces the final natural language answer."""
    print("--- [NODE: RESPONDER] ---")
    start_time = time.time()
    
    if state.get('intent') == 'chat':
        return {"latency_ms": int((time.time() - start_time) * 1000)}

    if state.get('error'):
         print(f"Final response state contains an error: {state['error']}")
         latency = state.get("latency_ms", 0) + int((time.time() - start_time) * 1000)
         
         # Use the ORIGINAL error and query for better diagnostics
         orig_error = state.get("first_error", state['error'])
         orig_query = state.get("first_failing_query", state.get("sql_query"))

         error_content = (
             f"**Database Error**: {orig_error}\n\n"
             f"**Original Failing Query**: `{orig_query}`\n\n"
             "I tried to fix it but couldn't. Please try rephrasing your question."
         )
         
         error_msg = AIMessage(content=error_content)
         return {
             "messages": [error_msg],
             "latency_ms": latency
         }

    # Format the result for the LLM
    data = state.get('sql_result', [])
    if isinstance(data, list):
        if len(data) > 20:
            formatted_data = str(data[:20]) + "\n... (truncated for brevity)"
        else:
            formatted_data = str(data)
    else:
        formatted_data = str(data)

    print(f"Formatting natural language answer for {len(data)} results...")

    prompt = RESPONSE_PROMPT.format(
        question=state['question'],
        sql_query=state['sql_query'],
        sql_result=formatted_data
    )
    
    messages = [
        SystemMessage(content=prompt)
    ]
    
    response = llm.invoke(messages)
    print(f"Final Answer Generated.")
    
    latency = state.get("latency_ms", 0) + int((time.time() - start_time) * 1000)
    return {
        "messages": [response],
        "latency_ms": latency
    }
