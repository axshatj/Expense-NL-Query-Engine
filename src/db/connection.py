import sqlite3
import logging
from pathlib import Path
from typing import Any, List, Dict, Tuple, Optional
from src.config import DATABASE_PATH

logger = logging.getLogger(__name__)
SCHEMA_PATH = Path(__file__).parent / "schema.sql"

def get_db_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """
    Establishes and returns a SQLite database connection.
    Configures row_factory to sqlite3.Row for dictionary-like access.
    Supports URI mode if db_path starts with file:
    """
    target_path = db_path if db_path is not None else DATABASE_PATH
    logger.debug(f"Opening SQLite database connection to: {target_path}")
    
    is_uri = isinstance(target_path, str) and target_path.startswith("file:")
    
    # Ensure parent directory exists if not an in-memory database or URI
    if target_path != ":memory:" and not is_uri:
        Path(target_path).parent.mkdir(parents=True, exist_ok=True)
        
    try:
        conn = sqlite3.connect(target_path, uri=is_uri)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn
    except Exception as e:
        logger.error(f"Failed to open database connection to {target_path}: {e}")
        raise e

def init_db(db_path: Optional[str] = None, conn: Optional[sqlite3.Connection] = None) -> sqlite3.Connection:
    """
    Initializes database schema using schema.sql.
    Returns the connection object if an existing conn was passed, or a new connection.
    """
    logger.info("Initializing database schema...")
    should_close = conn is None
    connection = conn if conn is not None else get_db_connection(db_path)
    
    try:
        with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
            schema_sql = f.read()
        connection.executescript(schema_sql)
        connection.commit()
        logger.info("Database schema initialized and committed successfully.")
        return connection
    except Exception as e:
        logger.error(f"Failed to initialize database schema: {e}")
        raise e
    finally:
        if should_close:
            connection.close()

def execute_query(
    query: str,
    params: Tuple[Any, ...] | List[Any] = (),
    db_path: Optional[str] = None,
    conn: Optional[sqlite3.Connection] = None
) -> List[Dict[str, Any]]:
    """
    Executes a SELECT query with parameters and returns rows as a list of dicts.
    """
    logger.debug(f"Executing SQL query: '{query}' with params: {params}")
    should_close = conn is None
    connection = conn if conn is not None else get_db_connection(db_path)
    
    try:
        cursor = connection.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        result = [dict(row) for row in rows]
        logger.debug(f"SQL query fetched {len(result)} rows.")
        return result
    except Exception as e:
        logger.error(f"Database query execution error for query '{query}': {e}")
        raise e
    finally:
        if should_close:
            connection.close()

def execute_statement(
    statement: str,
    params: Tuple[Any, ...] | List[Any] = (),
    db_path: Optional[str] = None,
    conn: Optional[sqlite3.Connection] = None
) -> int:
    """
    Executes an INSERT, UPDATE, or DELETE statement with parameters.
    Returns the lastrowid or rowcount.
    """
    logger.debug(f"Executing SQL statement: '{statement}' with params: {params}")
    should_close = conn is None
    connection = conn if conn is not None else get_db_connection(db_path)
    
    try:
        cursor = connection.cursor()
        cursor.execute(statement, params)
        connection.commit()
        ret_val = cursor.lastrowid if cursor.lastrowid else cursor.rowcount
        logger.debug(f"SQL statement completed. Return value (lastrowid/rowcount): {ret_val}")
        return ret_val
    except Exception as e:
        logger.error(f"Database statement execution error for '{statement}': {e}")
        raise e
    finally:
        if should_close:
            connection.close()

def execute_many(
    statement: str,
    params_list: List[Tuple[Any, ...]] | List[List[Any]],
    db_path: Optional[str] = None,
    conn: Optional[sqlite3.Connection] = None
) -> int:
    """
    Executes executemany for batch insertions.
    """
    logger.debug(f"Executing SQL batch statement: '{statement}' for {len(params_list)} items")
    should_close = conn is None
    connection = conn if conn is not None else get_db_connection(db_path)
    
    try:
        cursor = connection.cursor()
        cursor.executemany(statement, params_list)
        connection.commit()
        logger.debug(f"SQL batch statement completed. Affected rowcount: {cursor.rowcount}")
        return cursor.rowcount
    except Exception as e:
        logger.error(f"Database batch statement execution error for '{statement}': {e}")
        raise e
    finally:
        if should_close:
            connection.close()
