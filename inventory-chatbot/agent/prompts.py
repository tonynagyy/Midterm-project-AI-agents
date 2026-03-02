import sqlite3
SYSTEM_PROMPT = ''
REPLAN_PROMPT = ''
RESPONSE_PROMPT = ''

def get_schema_string(db_path: str) -> str:
    """Connects to the DB and returns the CREATE TABLE statements."""
    pass