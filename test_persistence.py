import logging
from careerloop.session.session_store import SessionStore, Session
from careerloop.session.states import UserState
from careerloop.memory.connection import DatabaseManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("persistence_test")

def run_test():
    logger.info("Initializing DatabaseManager...")
    db = DatabaseManager()
    
    logger.info("Initializing SessionStore...")
    store = SessionStore(db_manager=db)
    
    test_user_id = "test_persistence_user_123"
    
    logger.info(f"Clearing old test session for {test_user_id} (if any)...")
    store.delete_session(test_user_id)
    
    logger.info(f"Creating a new session with artifact context...")
    new_session = Session(
        user_id=test_user_id,
        state=UserState.REVIEWING_BRIEF,
        active_artifact_type="daily_brief",
        active_brief_id="brief_001",
        current_selection_index=5
    )
    
    save_result = store.save_session(new_session)
    logger.info(f"Save Result: {save_result}")
    
    logger.info(f"Reloading session from database...")
    reloaded_session = store.get_session(test_user_id)
    
    logger.info("--- Validation ---")
    logger.info(f"State: {reloaded_session.state.value} (Expected: {UserState.REVIEWING_BRIEF.value})")
    logger.info(f"Active Artifact Type: {reloaded_session.active_artifact_type} (Expected: daily_brief)")
    logger.info(f"Active Brief ID: {reloaded_session.active_brief_id} (Expected: brief_001)")
    logger.info(f"Selection Index: {reloaded_session.current_selection_index} (Expected: 5)")
    
    # Assertions
    assert reloaded_session.state == UserState.REVIEWING_BRIEF, "State mismatch"
    assert reloaded_session.active_artifact_type == "daily_brief", "Artifact type mismatch"
    assert reloaded_session.active_brief_id == "brief_001", "Brief ID mismatch"
    assert reloaded_session.current_selection_index == 5, "Selection index mismatch"
    
    logger.info("SUCCESS: Database persistence is fully functional. Active context is surviving the round trip!")
    
    # Cleanup
    logger.info("Cleaning up test user...")
    store.delete_session(test_user_id)

if __name__ == "__main__":
    run_test()
