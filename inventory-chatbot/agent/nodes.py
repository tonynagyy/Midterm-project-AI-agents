import sqlite3
import os
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from .state import AgentState
from .prompts import SYSTEM_PROMPT, REPLAN_PROMPT, RESPONSE_PROMPT, get_schema_string
llm = ChatOpenAI(model='gpt-5-mini', temperature=0)
DB_PATH = 'inventory_chatbot.db'

def sql_generator_node(state: AgentState):
    """Generates the initial SQL query based on the question."""
    pass

def sql_executor_node(state: AgentState):
    """Executes the SQL query against the database."""
    pass

def sql_corrector_node(state: AgentState):
    """Refines the SQL if an error occurred."""
    pass

def responder_node(state: AgentState):
    pass