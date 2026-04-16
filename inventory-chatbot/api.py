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
    response: str

api_app = FastAPI(title="Inventory Chatbot API")

@api_app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    try:
        config = {"configurable": {"thread_id": request.session_id}}
        
        initial_state = {
            "question": request.message,
            "messages": [HumanMessage(content=request.message)],
            "revision_count": 0,
            "latency_ms": 0,
            "token_usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        }
        
        final_state = app.invoke(initial_state, config=config)
        
        # Extract Answer
        last_message = final_state["messages"][-1].content
        
        return ChatResponse(
            response=last_message
        )
        
    except Exception as e:
        return ChatResponse(
            response=f"An error occurred: {str(e)}"
        )

@api_app.get("/api/history/{session_id}")
async def history_endpoint(session_id: str):
    try:
        config = {"configurable": {"thread_id": session_id}}
        state = app.get_state(config)
        messages = []
        if state and hasattr(state, "values") and "messages" in state.values:
            for msg in state.values["messages"]:
                role = "user" if getattr(msg, "type", "") == "human" else "assistant"
                messages.append({"role": role, "content": msg.content})
        return {"messages": messages}
    except Exception as e:
        return {"messages": [], "error": str(e)}

if __name__ == "__main__":
    import uvicorn
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))
    
    print(f"Starting API server on {host}:{port}")
    uvicorn.run(api_app, host=host, port=port)
