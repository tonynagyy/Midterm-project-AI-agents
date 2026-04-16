# Evaluation Script with 3 Metrics
import os
from dotenv import load_dotenv
from langsmith import Client
from agent.graph import app
from langchain_core.messages import HumanMessage

load_dotenv()

client = Client()

def target(inputs: dict) -> dict:
    """The application logic to evaluate. Inputs are automatically sent here."""
    config = {"configurable": {"thread_id": "eval_thread"}}
    
    initial_state = {
        "question": inputs["question"],
        "messages": [HumanMessage(content=inputs["question"])],
        "revision_count": 0,
        "token_usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    }
    
    final_state = app.invoke(initial_state, config=config)
    
    return {"answer": final_state["messages"][-1].content}

def correctness_evaluator(inputs: dict, outputs: dict, reference_outputs: dict) -> dict:
    """Evaluates if the AI's actual answer contains the expected keywords."""
    expected = reference_outputs.get("answer", "")
    actual = outputs.get("answer", "")
    
    score = 1 if expected.lower() in actual.lower() else 0
    if "An error occurred" in actual or "I cannot find" in actual:
        score = 0
        
    return {"key": "correctness", "score": score}

def conciseness_evaluator(inputs: dict, outputs: dict, reference_outputs: dict) -> dict:
    """Evaluates if the answer is less than 500 characters."""
    actual = outputs.get("answer", "")
    score = 1 if len(actual) < 500 else 0
    return {"key": "conciseness", "score": score}

def reliability_evaluator(inputs: dict, outputs: dict, reference_outputs: dict) -> dict:
    """Evaluates if there was no catastrophic error output."""
    actual = outputs.get("answer", "")
    score = 0 if "An error occurred" in actual else 1
    return {"key": "reliability", "score": score}

def run_evaluation():
    dataset_name = "Inventory-Chatbot-DS-v2"
    
    if not client.has_dataset(dataset_name=dataset_name):
        dataset = client.create_dataset(
            dataset_name=dataset_name, 
            description="Testing standard chat and SQL outputs"
        )
        examples = [
            {
                "inputs": {"question": "What is the total value of assets?"},
                "outputs": {"answer": "asset"},
            },
            {
                "inputs": {"question": "Hi, who are you?"},
                "outputs": {"answer": "inventory"},
            },
            {
                "inputs": {"question": "Show me active customers"},
                "outputs": {"answer": "customer"},
            }
        ]
        client.create_examples(dataset_id=dataset.id, examples=examples)

    print(f"Running evaluation against dataset: {dataset_name}...")
    
    experiment_results = client.evaluate(
        target,
        data=dataset_name,
        evaluators=[correctness_evaluator, conciseness_evaluator, reliability_evaluator],
        experiment_prefix="experiment-inventory-run",
        max_concurrency=2,
    )
    
    print("Evaluation Complete. Check LangSmith UI for detailed metrics.")

if __name__ == "__main__":
    if "LANGCHAIN_API_KEY" not in os.environ:
        print("Please set LANGCHAIN_API_KEY in your .env file to enable LangSmith tracking.")
    else:
        run_evaluation()
