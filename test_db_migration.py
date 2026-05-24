import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from careerloop.memory.connection import get_db_manager
from careerloop.session.session_store import SessionStore, Session
from careerloop.session.states import UserJourneyState

def run_test():
    print("Initializing Database Manager...")
    db = get_db_manager()
    print("Database Initialized.")
    
    print("Initializing Session Store...")
    store = SessionStore(db)
    
    test_user_id = "test_user_123"
    
    print(f"Fetching session for {test_user_id}...")
    session = store.get_session(test_user_id)
    print(f"Retrieved session: {session}")
    
    print("Updating session state to PROFILE_READY...")
    session.state = UserJourneyState.PROFILE_READY
    store.save_session(session)
    
    print("Refetching session...")
    updated_session = store.get_session(test_user_id)
    print(f"Updated session: {updated_session}")
    
    if updated_session.state == UserJourneyState.PROFILE_READY:
        print("SUCCESS: State persistence works.")
    else:
        print("ERROR: State persistence failed.")

if __name__ == "__main__":
    run_test()
