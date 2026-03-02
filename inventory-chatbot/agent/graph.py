from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from .state import AgentState
from .nodes import (
    router_node, 
    chat_node, 
    sql_generator_node, 
    sql_executor_node, 
    sql_corrector_node, 
    responder_node
)

def router_logic(state: AgentState):
    """Routes to either SQL generator or general chat."""
    if state.get("intent") == "sql":
        return "generator"
    return "chat"

def should_continue(state: AgentState):
    """Decision logic after SQL execution."""
    if state.get("error"):
        if state.get("revision_count", 0) < 3:
            return "corrector"
    return "responder"

workflow = StateGraph(AgentState)

# Add nodes
workflow.add_node('router', router_node)
workflow.add_node('chat', chat_node)
workflow.add_node('generator', sql_generator_node)
workflow.add_node('executor', sql_executor_node)
workflow.add_node('corrector', sql_corrector_node)
workflow.add_node('responder', responder_node)

# Set entry point
workflow.set_entry_point('router')

# Define edges
workflow.add_conditional_edges(
    'router', 
    router_logic, 
    {'generator': 'generator', 'chat': 'chat'}
)

workflow.add_edge('chat', 'responder')
workflow.add_edge('generator', 'executor')

workflow.add_conditional_edges(
    'executor', 
    should_continue, 
    {'corrector': 'corrector', 'responder': 'responder'}
)

workflow.add_edge('corrector', 'executor')
workflow.add_edge('responder', END)

memory = MemorySaver()
app = workflow.compile(checkpointer=memory)