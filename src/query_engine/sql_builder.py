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
    translated_group_by = [
        "merchant_normalized" if col == "merchant" else col
        for col in ir.group_by
    ]

    if ir.intent == "list":
        select_clause = "*"
    else:
        metric = ir.metric or "sum"
        metric_expr = METRIC_MAP.get(metric, "SUM(amount)")
        if translated_group_by:
            group_cols = ", ".join(translated_group_by)
            select_clause = f"{group_cols}, {metric_expr} AS result"
        else:
            select_clause = f"{metric_expr} AS result"

    where_clause = f" WHERE {' AND '.join(where)}" if where else ""
    group_clause = f" GROUP BY {', '.join(translated_group_by)}" if translated_group_by else ""

    if ir.intent == "list":
        order_clause = " ORDER BY date DESC, id DESC"
    else:
        order_clause = ""

    limit_clause = f" LIMIT {int(ir.limit)}" if ir.limit else ""


    sql = f"SELECT {select_clause} FROM transactions{where_clause}{group_clause}{order_clause}{limit_clause}"
    return sql, params


def build_subscription_query(
    ir: QueryIR, override_date_range: Optional[DateRange] = None
) -> Tuple[str, List[Any]]:
    """
    Builds SQL query for subscription queries by identifying merchants with
    recurring transaction pattern (same merchant + similar amount in >=2 months).
    """
    target_date_range = override_date_range or ir.date_range
    start_date = target_date_range.start if target_date_range and target_date_range.start else "2000-01-01"
    end_date = target_date_range.end if target_date_range and target_date_range.end else "2026-08-11"

    recurrence_sql = """
        SELECT merchant_normalized
        FROM transactions
        WHERE transaction_type = 'debit'
        GROUP BY merchant_normalized, ROUND(amount / 10.0) * 10
        HAVING COUNT(DISTINCT strftime('%Y-%m', date)) >= 2
    """

    if ir.group_by:
        group_cols = []
        for col in ir.group_by:
            if col == "merchant":
                group_cols.append("merchant_normalized")
            else:
                group_cols.append(col)
        select_clause = f"{', '.join(group_cols)}, SUM(amount) AS result"
        group_clause = f" GROUP BY {', '.join(group_cols)}"
    else:
        select_clause = "SUM(amount) AS result"
        group_clause = ""

    sql = f"""
        SELECT {select_clause}
        FROM transactions
        WHERE transaction_type = 'debit'
          AND date BETWEEN ? AND ?
          AND merchant_normalized IN ({recurrence_sql})
        {group_clause}
    """
    # Clean up whitespace/newlines
    sql = " ".join(sql.split())
    params = [start_date, end_date]
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

    if ir.is_subscription_query:
        if ir.intent == "compare":
            primary_query = build_subscription_query(ir, override_date_range=ir.date_range)
            compare_query = build_subscription_query(ir, override_date_range=ir.compare_date_range)
            return {
                "primary": primary_query,
                "compare": compare_query
            }
        return build_subscription_query(ir)

    if ir.intent == "compare":
        primary_query = build_single_query(ir, override_date_range=ir.date_range)
        compare_query = build_single_query(ir, override_date_range=ir.compare_date_range)
        return {
            "primary": primary_query,
            "compare": compare_query
        }

    return build_single_query(ir)

