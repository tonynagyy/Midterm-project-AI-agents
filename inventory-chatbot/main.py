import sys
import os
from agent.graph import app

def main():
    print("========================================")
    print("Welcome to the Inventory Chatbot (CLI)")
    print("Type 'exit' or 'quit' to end the session.")
    print("========================================\n")

    while True:
        try:
            user_input = input("You: ").strip()
            
            if not user_input:
                continue
                
            if user_input.lower() in ['exit', 'quit']:
                print("Inventory Bot: Goodbye!")
                break

            # Run the graph
            state_input = {"question": user_input}
            config = {"configurable": {"thread_id": "cli_user"}}
            
            # Running the graph
            result = app.invoke(state_input, config=config)
            
            # The responder_node puts the AIMessage in 'messages'
            if 'messages' in result and len(result['messages']) > 0:
                final_response = result['messages'][-1].content
                print(f"\nInventory Bot: {final_response}\n")
            else:
                print("\nInventory Bot: I'm sorry, I couldn't process that request.\n")

        except KeyboardInterrupt:
            print("\nInventory Bot: Goodbye!")
            break
        except Exception as e:
            print(f"\nError: {str(e)}\n")

if __name__ == "__main__":
    main()
