"""
Stage 2 SQL Builder: Converts JSON QueryIR into safe, parameterized SQLite queries.
"""
from typing import Tuple, List, Dict, Any, Union, Optional
from src.models.ir import QueryIR, DateRange

METRIC_MAP = {
    "sum": "SUM(amount)",
    "count": "COUNT(*)",
    "avg": "AVG(amount)",
    "max": "MAX(amount)",
    "min": "MIN(amount)",
}


def build_single_query(
    ir: QueryIR, override_date_range: Optional[DateRange] = None
) -> Tuple[str, List[Any]]:
    """
    Builds a single parameterized SQL query string and parameter list for a QueryIR object.
    Can override the date range (used for comparison queries).
    """
    where: List[str] = []
    params: List[Any] = []

    # 1. Transaction type filter
    if ir.filters.transaction_type:
        where.append("transaction_type = ?")
        params.append(ir.filters.transaction_type)

    # 2. Date range filter
    target_date_range = override_date_range or ir.date_range
    if target_date_range and target_date_range.start and target_date_range.end:
        where.append("date BETWEEN ? AND ?")
        params.extend([target_date_range.start, target_date_range.end])

    # 3. Exclude transfers filter
    if ir.filters.exclude_transfers:
        where.append("category != ?")
        params.append("transfers")

    # 4. Category filter
    if ir.filters.category:
        placeholders = ", ".join(["?"] * len(ir.filters.category))
        where.append(f"category IN ({placeholders})")
        params.extend(ir.filters.category)

    # 5. Merchant filter (case-insensitive normalized substring match)
    if ir.filters.merchant:
        merchant_clauses = " OR ".join(["merchant_normalized LIKE ?"] * len(ir.filters.merchant))
        where.append(f"({merchant_clauses})")
        params.extend([f"%{m}%" for m in ir.filters.merchant])

    # 6. Amount filters
    if ir.filters.amount_min is not None:
        where.append("amount >= ?")
        params.append(ir.filters.amount_min)
    if ir.filters.amount_max is not None:
        where.append("amount <= ?")
        params.append(ir.filters.amount_max)

    # Build SELECT clause
    if ir.intent == "list":
        select_clause = "*"
    else:
        metric = ir.metric or "sum"
        metric_expr = METRIC_MAP.get(metric, "SUM(amount)")
        if ir.group_by:
            group_cols = ", ".join(ir.group_by)
            select_clause = f"{group_cols}, {metric_expr} AS result"
        else:
            select_clause = f"{metric_expr} AS result"

    where_clause = f" WHERE {' AND '.join(where)}" if where else ""
    group_clause = f" GROUP BY {', '.join(ir.group_by)}" if ir.group_by else ""

    if ir.intent == "list":
        order_clause = " ORDER BY date DESC, id DESC"
    else:
        order_clause = ""

    limit_clause = f" LIMIT {int(ir.limit)}" if ir.limit else ""

    sql = f"SELECT {select_clause} FROM transactions{where_clause}{group_clause}{order_clause}{limit_clause}"
    return sql, params


def build_query(
    ir: QueryIR
) -> Union[Tuple[str, List[Any]], Dict[str, Tuple[str, List[Any]]]]:
    """
    Builds SQL query/queries for a QueryIR object.
    For intent == "compare", returns a dict with 'primary' and 'compare' query tuples.
    For intent == "unrelated", returns empty query tuple.
    Otherwise returns (sql, params) tuple.
    """
    if ir.intent == "unrelated":
        return ("", [])

    if ir.intent == "compare":
        primary_query = build_single_query(ir, override_date_range=ir.date_range)
        compare_query = build_single_query(ir, override_date_range=ir.compare_date_range)
        return {
            "primary": primary_query,
            "compare": compare_query
        }

    return build_single_query(ir)
