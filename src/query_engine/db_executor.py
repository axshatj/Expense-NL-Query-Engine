"""
Stage 2 DB Executor: Executes SQL queries generated from QueryIR against SQLite database.
"""
import sqlite3
import logging
from typing import Dict, Any, Optional
from src.models.ir import QueryIR
from src.db.connection import execute_query
from src.query_engine.sql_builder import build_query

logger = logging.getLogger(__name__)

OUT_OF_DOMAIN_MESSAGE = (
    "I am an expense tracking assistant. I can only answer questions related to your "
    "personal transactions, spending, and accounts."
)


def execute_ir(
    ir: QueryIR,
    conn: Optional[sqlite3.Connection] = None,
    db_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Safely executes the query corresponding to a QueryIR object.
    Routes unrelated intents to non-DB refusal message.
    """
    if ir.intent == "unrelated":
        logger.info("Query intent is 'unrelated'. Routing to non-DB refusal message.")
        return {
            "status": "unrelated",
            "message": OUT_OF_DOMAIN_MESSAGE,
            "data": None
        }

    logger.info(f"Executing QueryIR: intent='{ir.intent}', metric='{ir.metric}', group_by={ir.group_by}")

    query_obj = build_query(ir)

    if ir.intent == "compare":
        primary_sql, primary_params = query_obj["primary"]
        compare_sql, compare_params = query_obj["compare"]

        logger.debug(f"Executing comparison primary query: {primary_sql} with params {primary_params}")
        primary_rows = execute_query(primary_sql, primary_params, conn=conn, db_path=db_path)
        logger.debug(f"Executing comparison period query: {compare_sql} with params {compare_params}")
        compare_rows = execute_query(compare_sql, compare_params, conn=conn, db_path=db_path)

        if ir.group_by:
            primary_res = primary_rows
            compare_res = compare_rows
        else:
            primary_val = primary_rows[0]["result"] if primary_rows and primary_rows[0]["result"] is not None else 0.0
            compare_val = compare_rows[0]["result"] if compare_rows and compare_rows[0]["result"] is not None else 0.0
            primary_res = primary_val
            compare_res = compare_val

        logger.info(f"Comparison query execution complete. Primary: {primary_res}, Compare: {compare_res}")
        return {
            "status": "success",
            "intent": "compare",
            "metric": ir.metric,
            "primary_period": {
                "date_range": ir.date_range.model_dump() if ir.date_range else None,
                "result": primary_res,
                "sql": primary_sql
            },
            "compare_period": {
                "date_range": ir.compare_date_range.model_dump() if ir.compare_date_range else None,
                "result": compare_res,
                "sql": compare_sql
            }
        }

    sql, params = query_obj

    if ir.intent == "list":
        logger.debug(f"Executing list query: {sql} with params {params}")
        rows = execute_query(sql, params, conn=conn, db_path=db_path)
        logger.info(f"List query execution complete. Found {len(rows)} transactions.")
        return {
            "status": "success",
            "intent": "list",
            "count": len(rows),
            "data": rows,
            "query_sql": sql
        }

    # Aggregate or Trend
    logger.debug(f"Executing aggregate/trend query: {sql} with params {params}")
    rows = execute_query(sql, params, conn=conn, db_path=db_path)

    if ir.group_by:
        data = rows
        logger.info(f"Aggregate query with group_by complete. Found {len(data)} groups.")
    else:
        if rows and rows[0]["result"] is not None:
            data = rows[0]["result"]
        else:
            data = 0 if ir.metric == "count" else 0.0
        logger.info(f"Aggregate query complete. Result: {data}")

    return {
        "status": "success",
        "intent": ir.intent,
        "metric": ir.metric,
        "date_range": ir.date_range.model_dump() if ir.date_range else None,
        "data": data,
        "query_sql": sql
    }
