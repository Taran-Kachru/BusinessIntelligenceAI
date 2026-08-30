import os
import duckdb
import pandas as pd
from typing import Generator, Any
from dotenv import load_dotenv
from .models import UserContext

load_dotenv()

DEMO_TODAY = os.getenv("DEMO_TODAY", "2026-08-18")

# Module-level connection
_conn = None

def init_db(data_dir: str = 'data'):
    """
    Initializes the DuckDB in-memory database.
    Loads CSV data and creates empty tables.
    """
    global _conn
    _conn = duckdb.connect(':memory:')
    
    # Tables to load from CSV
    csv_files = [
        'sales_transactions',
        'marketing_spend',
        'customer_events',
        'context_notes'
    ]
    
    for tbl in csv_files:
        path = os.path.join(data_dir, f"{tbl}.csv")
        if os.path.exists(path):
            _conn.execute(f"CREATE TABLE {tbl} AS SELECT * FROM read_csv_auto('{path}')")
        else:
            print(f"Warning: {path} not found. Table {tbl} not created.")
            
    # Create shared calendar table (daily date spine from 2026-01-01 to 2026-08-18)
    _conn.execute("""
        CREATE TABLE calendar AS 
        SELECT current_date::DATE AS date 
        FROM generate_series(DATE '2026-01-01', DATE '2026-08-18', INTERVAL 1 DAY) AS t(current_date)
    """)
    
    # Create empty feedback_store table
    _conn.execute("""
        CREATE TABLE feedback_store (
            insight_id VARCHAR,
            feedback_type VARCHAR,
            rating INTEGER,
            correction_text VARCHAR,
            target VARCHAR,
            target_id VARCHAR,
            timestamp TIMESTAMP
        )
    """)
    
    # Create empty access_log table
    _conn.execute("""
        CREATE TABLE access_log (
            timestamp TIMESTAMP,
            user_id VARCHAR,
            resource VARCHAR,
            action VARCHAR,
            allowed BOOLEAN,
            details VARCHAR
        )
    """)

def get_db_connection():
    """Returns the raw DuckDB connection for direct use in pipeline modules."""
    if _conn is None:
        raise Exception("Database not initialized. Call init_db() first.")
    return _conn

def get_db() -> Generator[Any, None, None]:
    """FastAPI dependency that yields a cursor from the main connection and closes it after use."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        yield cursor
    finally:
        cursor.close()

def secure_query(cursor, sql: str, params: dict, user_context: UserContext) -> pd.DataFrame:
    """
    Executes a query with Row-Level Security applied.
    Takes a UserContext and enforces region/PII restrictions.
    """
    # 1. Apply region filtering if restricted
    if user_context.allowed_regions and "ALL" not in user_context.allowed_regions:
        regions_str = ", ".join([f"'{r}'" for r in user_context.allowed_regions])
        # Wrap query in a subquery to apply region filter.
        # Note: In practice this requires the base query to return a 'region' column.
        secure_sql = f"SELECT * FROM ({sql}) AS base_query WHERE region IN ({regions_str})"
    else:
        secure_sql = sql
        
    # 2. Execute query and log access
    try:
        if params:
            df = cursor.execute(secure_sql, params).fetchdf()
        else:
            df = cursor.execute(secure_sql).fetchdf()
        allowed = True
    except Exception as e:
        allowed = False
        raise e
    finally:
        # Convert params to string for logging purposes
        params_str = str(params) if params else None
        
        # Log access
        try:
            cursor.execute(
                "INSERT INTO access_log VALUES (current_timestamp, ?, ?, 'read', ?, ?)",
                [user_context.user_id, 'secure_query', allowed, sql]
            )
        except Exception:
            pass # Failsafe against logging errors
            
    # 3. Strip/replace PII
    if not user_context.can_view_pii:
        if 'nps_comment' in df.columns:
            df['nps_comment'] = 'REDACTED'
            
    return df
