import os
from contextlib import contextmanager
from langgraph.checkpoint.postgres import PostgresSaver

@contextmanager
def get_checkpointer():
    """
    Returns a PostgresSaver connected to the Supabase database.
    By using the user's phone number or email as the thread_id, 
    state is persisted flawlessly across async webhook hits.
    """
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL environment variable is required")
        
    with PostgresSaver.from_conn_string(db_url) as checkpointer:
        try:
            checkpointer.setup()
        except Exception as e:
            msg = str(e).lower()
            # Some environments can throw on repeated setup/prepared statements.
            if "already exists" not in msg:
                raise
        yield checkpointer
