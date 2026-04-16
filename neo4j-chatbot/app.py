import uuid
import streamlit as st

# We must set page_config as the first Streamlit command
st.set_page_config(page_title="Football Knowledge Graph", page_icon="⚽", layout="wide")

import logging
from agent.langgraph_orchestrator import LangGraphOrchestrator
from agent.logging_setup import setup_logging
from config import LLM_MODEL, LLM_PROVIDER, LONG_MEMORY_ENABLED, SHORT_MEMORY_TURNS

setup_logging()
logger = logging.getLogger(__name__)

# -------------------------------------------------------------------
# Initialization
# -------------------------------------------------------------------

@st.cache_resource
def get_chatbot_orchestrator():
    """
    Initialize and cache the LangGraph orchestrator so it persists across reruns.
    """
    return LangGraphOrchestrator()

try:
    orchestrator = get_chatbot_orchestrator()
except Exception as exc:
    logger.exception("Failed to initialize LangGraph orchestrator in Streamlit.")
    st.error(f"Failed to initialize chatbot components. Error: {exc}")
    st.stop()

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

# -------------------------------------------------------------------
# UI Layout
# -------------------------------------------------------------------

st.title("⚽ Champions League Graph Bot")
st.markdown(f"Interact with the football knowledge graph using {LLM_MODEL.upper()} ({LLM_PROVIDER.upper()}).")
st.caption("Supported LLM providers: ollama, openai, groq, lmstudio")

# Sidebar
with st.sidebar:
    st.header("Settings & Info")
    debug_mode = st.toggle("Debug Mode", value=False, help="Show raw queries and intents for troubleshooting.")
    
    st.info(f"**Session ID:** `{st.session_state.session_id}`")
    st.info(f"**Provider:** {LLM_PROVIDER.upper()}")
    st.info(f"**Model:** {LLM_MODEL}")
    st.info(f"**Short Memory Turns:** {SHORT_MEMORY_TURNS}")
    st.info(f"**Long Memory:** {'Enabled' if LONG_MEMORY_ENABLED else 'Disabled'}")

    if debug_mode and LONG_MEMORY_ENABLED and st.button("Show Long Memory Snapshot"):
        snapshot = orchestrator.peek_long_memory(st.session_state.session_id, limit=8)
        if snapshot:
            st.json(snapshot)
        else:
            st.caption("No long-memory entries saved yet for this session.")
    
    if st.button("Clear Chat"):
        st.session_state.messages = []
        st.session_state.session_id = str(uuid.uuid4())
        st.rerun()

    st.markdown("---")
    st.markdown("### Example Prompts")
    st.markdown("**Inquire:**")
    st.markdown("- Who does Lionel Messi play for?")
    st.markdown("- Who is the manager of Manchester City?")
    st.markdown("**Add:**")
    st.markdown("- Add the fact that Cody Gakpo plays for Liverpool.")
    st.markdown("**Update:**")
    st.markdown("- Update the fact that Kylian Mbappé plays for Real Madrid to Paris Saint-Germain.")
    st.markdown("**Delete:**")
    st.markdown("- Remove the fact that Kevin De Bruyne plays for Manchester City.")
    st.markdown("**Chitchat:**")
    st.markdown("- Hello! How are you doing?")

# -------------------------------------------------------------------
# Chat History
# -------------------------------------------------------------------

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        
        # Display debug info if available
        if message.get("debug") and debug_mode:
            debug_info = message["debug"]
            with st.expander("🛠️ Raw Debug Data"):
                st.write(f"**Intent:** {debug_info.get('intent')}")
                st.write(f"**Latency:** {debug_info.get('latency', 0):.2f} ms")
                
                if debug_info.get("cypher"):
                    st.code(debug_info["cypher"], language="cypher")
                if debug_info.get("raw_results") is not None:
                    st.json(debug_info["raw_results"])

# -------------------------------------------------------------------
# Chat Input
# -------------------------------------------------------------------

if prompt := st.chat_input("Ask about Champions League football..."):
    # Add user message to state
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Process with the agent
    with st.chat_message("assistant"):
        with st.spinner("Processing..."):
            debug_data = {}
            response_text = ""
            
            try:
                result = orchestrator.run_turn(
                    user_input=prompt,
                    thread_id=st.session_state.session_id,
                )
                response_text = result.get("response", "")

                debug_data["intent"] = result.get("intent")
                debug_data["cypher"] = result.get("cypher_query")
                debug_data["raw_results"] = result.get("raw_results")
                debug_data["latency"] = result.get("latency_ms", 0)
                debug_data["metrics"] = result.get("metrics", {})
                debug_data["memory_turns"] = result.get("memory_turns", 0)
                debug_data["long_memory_hits"] = result.get("long_memory_hits", 0)

                if result.get("error"):
                    debug_data["error"] = result.get("error")
            except Exception as exc:
                logger.exception("Streamlit turn failed.")
                response_text = f"I'm sorry, I encountered an error: {exc}"
                debug_data["error"] = str(exc)
            
            # Display response
            st.markdown(response_text)
            
            # Optional Debug Output in current turn
            if debug_mode and debug_data:
                with st.expander("🛠️ Raw Debug Data"):
                    st.write(f"**Intent:** {debug_data.get('intent')}")
                    st.write(f"**Latency:** {debug_data.get('latency', 0):.2f} ms")
                    st.write(f"**Memory Turns:** {debug_data.get('memory_turns', 0)}")
                    st.write(f"**Long Memory Hits:** {debug_data.get('long_memory_hits', 0)}")
                    if debug_data.get("cypher"):
                        st.code(debug_data["cypher"], language="cypher")
                    if debug_data.get("raw_results") is not None:
                        st.json(debug_data["raw_results"])
                    if debug_data.get("metrics"):
                        st.json(debug_data["metrics"])

            # Save the message and state
            st.session_state.messages.append({
                "role": "assistant",
                "content": response_text,
                "debug": debug_data
            })
