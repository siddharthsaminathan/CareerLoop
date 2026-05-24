import os
from contextlib import contextmanager
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg_pool import ConnectionPool

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
        
    connection_kwargs = {
        "autocommit": True,
        "prepare_threshold": None,
    }
    
    with ConnectionPool(conninfo=db_url, kwargs=connection_kwargs, timeout=3) as pool:
        checkpointer = PostgresSaver(pool)
        try:
            checkpointer.setup()
        except Exception as e:
            msg = str(e).lower()
            if "already exists" not in msg:
                raise
        yield checkpointer
