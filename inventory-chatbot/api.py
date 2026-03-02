import os
from typing import Optional, Dict, Any
from fastapi import FastAPI
from pydantic import BaseModel
from dotenv import load_dotenv
from agent.graph import app
from langchain_core.messages import HumanMessage

load_dotenv()

PROVIDER = os.getenv("PROVIDER", "ollama")
MODEL_NAME = os.getenv("MODEL_NAME", "mistral")

class ChatRequest(BaseModel):
    session_id: str
    message: str
    context: Optional[Dict[str, Any]] = {}

class ChatResponse(BaseModel):
    natural_language_answer: str
    sql_query: Optional[str]
    token_usage: Dict[str, int]
    latency_ms: int
    provider: str
    model: str
    status: str

api_app = FastAPI(title="Inventory Chatbot API")

@api_app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    try:
        # Prepare configuration for LangGraph (for multi-session memory)
        config = {"configurable": {"thread_id": request.session_id}}
        
        initial_state = {
            "question": request.message,
            "messages": [HumanMessage(content=request.message)],
            "revision_count": 0,
            "latency_ms": 0,
            "token_usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        }
        
        # Run the LangGraph
        final_state = app.invoke(initial_state, config=config)
        
        # Extract Answer
        last_message = final_state["messages"][-1].content
        
        # Construct Response
        return ChatResponse(
            natural_language_answer=last_message,
            sql_query=final_state.get("sql_query"),
            token_usage=final_state.get("token_usage", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}),
            latency_ms=final_state.get("latency_ms", 0),
            provider=PROVIDER,
            model=MODEL_NAME,
            status="ok"
        )
        
    except Exception as e:
        # Error handling as per requirements
        return ChatResponse(
            natural_language_answer=f"An error occurred: {str(e)}",
            sql_query=None,
            token_usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            latency_ms=0,
            provider=PROVIDER,
            model=MODEL_NAME,
            status="error"
        )

if __name__ == "__main__":
    import uvicorn
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))
    
    print(f"Starting API server on {host}:{port}")
    uvicorn.run(api_app, host=host, port=port)
