import os
import json
import logging
import contextlib
from typing import List, Dict, Any, Optional, Union, Iterator

import psycopg2
from psycopg2.pool import SimpleConnectionPool
from psycopg2.extensions import connection
from psycopg2.extras import RealDictCursor, execute_values
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# Global connection pool object. Managed by init_db() and shutdown_db().
pool: Optional[SimpleConnectionPool] = None


def init_db(database_url, min_conn: int = 5, max_conn: int = 20) -> None:
    """
    Initialize the database connection pool.

    Args:
        min_conn: Minimum number of connections in the pool.
        max_conn: Maximum number of connections in the pool.

    Raises:
        ValueError: If the database URL is invalid or missing.
        RuntimeError: If the connection pool creation fails.
    """
    global pool
    try:
        pool = SimpleConnectionPool(
            min_conn, max_conn, dsn=database_url, sslmode="require"
        )
        logger.info(
            f"Database connection pool initialized successfully "
            f"(min_conn={min_conn}, max_conn={max_conn})."
        )
    except Exception as e:
        logger.error(f"Error initializing database connection pool: {e}", exc_info=True)
        raise RuntimeError(f"Failed to initialize pool: {e}") from e


def shutdown_db() -> None:
    """
    Close all database connections and shut down the pool.
    """
    global pool
    if pool:
        pool.closeall()
        logger.info("Database pool has been closed.")
        pool = None


@contextlib.contextmanager
def get_connection() -> Iterator[connection]:
    """
    Context manager for database connections from the pool.

    Yields:
        A psycopg2 database connection.

    Raises:
        RuntimeError: If the pool is not initialized.
    """
    if pool is None:
        raise RuntimeError("Database pool is not initialized. Call init_db() first.")
    conn = pool.getconn()
    try:
        yield conn
    finally:
        pool.putconn(conn)


def direct_query(
    query: str,
    params: Optional[Union[List[Any], Dict[str, Any]]] = None,
    fetch: bool = True,
) -> Optional[List[Dict[str, Any]]]:
    """
    Execute a SQL query directly using the global pool.

    Args:
        query: The SQL query to execute.
        params: Query parameters (list or dict) to avoid SQL injection.
        fetch: Whether to fetch and return results (True) or just execute (False).

    Returns:
        A list of dicts representing rows if `fetch=True`, otherwise None.
    """
    with get_connection() as conn:
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, params)
                if fetch:
                    rows = cur.fetchall()
                    return [dict(row) for row in rows]
                else:
                    conn.commit()
                    return None
        except Exception as e:
            conn.rollback()
            logger.error("Database query error", exc_info=True)
            logger.error(f"Query: {query}")
            logger.error(f"Params: {params}")
            raise


def direct_batch_insert(
    table: str,
    payload: List[Dict[str, Any]],
    chunk_size: int = 10_000,
    conflict_id: str = "id",
) -> None:
    """
    Insert multiple records into a database table in batches using the global pool.
    Performs an upsert based on the given conflict ID column.

    Args:
        table: Target table name.
        payload: List of dictionaries with the records to insert.
        chunk_size: Maximum number of records per batch.
        conflict_id: Column name to use for upsert conflict resolution.

    Raises:
        RuntimeError: If the database pool is not initialized.
        ValueError: If the payload is empty.
        Exception: If the operation fails.
    """
    if pool is None:
        raise RuntimeError("Database pool is not initialized. Call init_db() first.")
    if not payload:
        logger.warning("Empty payload, skipping batch insert.")
        return

    columns = list(payload[0].keys())
    column_names = ", ".join(columns)

    # Build the update clause (for ON CONFLICT) for each column except the conflict_id
    update_clause = ", ".join(
        f"{col} = EXCLUDED.{col}" for col in columns if col != conflict_id
    )
    sql = f"""
        INSERT INTO {table} ({column_names})
        VALUES %s
        ON CONFLICT ({conflict_id}) DO UPDATE
        SET {update_clause}
    """

    total_inserted = 0
    for i in range(0, len(payload), chunk_size):
        batch = payload[i : i + chunk_size]
        values = []
        for row in batch:
            row_values = []
            for col in columns:
                val = row[col]
                # Convert Python objects (dict, list) to JSON strings
                if isinstance(val, (dict, list)):
                    val = json.dumps(val)
                row_values.append(val)
            values.append(tuple(row_values))

        with get_connection() as conn:
            try:
                with conn.cursor() as cur:
                    execute_values(cur, sql, values)
                    conn.commit()
                    total_inserted += len(batch)
                    logger.info(
                        f"Inserted/Upserted {len(batch)} records into '{table}'."
                    )
            except Exception as e:
                conn.rollback()
                logger.error(f"Error in batch insert to table '{table}'", exc_info=True)
                raise

    logger.info(f"Total records inserted/upserted to '{table}': {total_inserted}")


class PostgreSQL:
    """
    A convenience wrapper that uses the same global connection pool.
    """

    def __init__(self, database_url) -> None:
        """
        Expects that init_db() has already been called.
        Raises:
            RuntimeError: If the global pool is not initialized.
        """
        init_db(database_url)
        if pool is None:
            raise RuntimeError("Database pool not initialized. Call init_db() first.")
        logger.info("PostgreSQL instance initialized with global connection pool.")

    def direct_query(
        self,
        query: str,
        params: Optional[Union[List[Any], Dict[str, Any]]] = None,
        fetch: bool = True,
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Same as the top-level direct_query, but accessed via an instance method.
        """
        return direct_query(query, params, fetch)

    def direct_batch_insert(
        self,
        table: str,
        payload: List[Dict[str, Any]],
        chunk_size: int = 10_000,
        conflict_id: str = "id",
    ) -> None:
        """
        Same as the top-level direct_batch_insert, but accessed via an instance method.
        """
        direct_batch_insert(table, payload, chunk_size, conflict_id)
