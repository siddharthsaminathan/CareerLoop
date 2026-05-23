import os
from dotenv import load_dotenv
load_dotenv()
from careerloop.transport.terminal_chat import TerminalChatAdapter
from careerloop.session.supervisor_graph import get_supervisor_graph
from careerloop.session.states import UserState
from careerloop.memory.checkpointer import get_checkpointer

def main():
    with get_checkpointer() as checkpointer:
        graph = get_supervisor_graph(checkpointer=checkpointer)
    transport = TerminalChatAdapter(supervisor_graph=graph)
    
    user_id = "testuser"
    
    # 1. Initial IDLE ping
    print("--- 1. Testing IDLE state ---")
    response = transport.receive({"user_id": user_id, "text": "hello", "metadata": {"current_state": UserState.IDLE}})
    print("Response 1:", response)
    
    # 2. Paste CV
    print("\n--- 2. Pasting CV ---")
    # Simulate being in ONBOARDING_WAITING_CV
    response = transport.receive({"user_id": user_id, "text": "This is my resume. I have 10 years of experience in Python and LangGraph.", "metadata": {"current_state": UserState.ONBOARDING_WAITING_CV}})
    print("Response 2:", response)
    
    if response and response.get("current_state"):
        print("Final state:", response.get("current_state"))
        
if __name__ == "__main__":
    main()
