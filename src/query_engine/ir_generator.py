import re
import json
import logging
from datetime import date
from typing import Optional, Dict, Any

from src.config import OPENAI_API_KEY, OPENAI_BASE_URL, LLM_MODEL, VALID_CATEGORIES
from src.prompts import load_prompt
from src.models.ir import QueryIR, DateRange, QueryFilters
from src.query_engine.date_resolver import get_resolved_date_ranges

logger = logging.getLogger(__name__)

IR_SCHEMA_STRING = """{
  "intent": "aggregate | list | compare | trend | unrelated",
  "metric": "sum | count | avg | max | min",
  "date_range": { "start": "YYYY-MM-DD", "end": "YYYY-MM-DD" },
  "compare_date_range": { "start": "YYYY-MM-DD", "end": "YYYY-MM-DD" },
  "filters": {
    "category": ["dining"],
    "merchant": ["amazon"],
    "transaction_type": "debit",
    "amount_min": null,
    "amount_max": null,
    "exclude_transfers": true
  },
  "group_by": ["category"],
  "limit": null
}"""

def _rule_based_ir_fallback(question: str, ref_date: date) -> QueryIR:
    """
    Fallback deterministic IR parser for common financial questions when LLM API key is absent.
    Ensures tests and offline development work seamlessly.
    """
    q_lower = question.lower()
    dates = get_resolved_date_ranges(ref_date)

    # 1. Out-of-domain / Unrelated detection
    if any(phrase in q_lower for phrase in ["python", "code", "sort", "script", "capital of", "weather", "who won"]):
        return QueryIR(intent="unrelated", metric=None, filters=QueryFilters())

    # Date range default: past 30 days or this year
    selected_range = DateRange(start=dates["this_month"][0], end=dates["this_month"][1])
    compare_range = None
    
    if "last month" in q_lower:
        selected_range = DateRange(start=dates["last_month"][0], end=dates["last_month"][1])
    elif "this year" in q_lower or "so far" in q_lower:
        selected_range = DateRange(start=dates["this_year"][0], end=dates["this_year"][1])
    elif "last 3 months" in q_lower or "3 months" in q_lower:
        selected_range = DateRange(start=dates["last_90_days"][0], end=dates["last_90_days"][1])
    elif "all time" in q_lower or "ever" in q_lower or "last 10" in q_lower or "top 5" in q_lower:
        selected_range = DateRange(start="2000-01-01", end=dates["today"][1])

    # Intent detection
    intent = "aggregate"
    limit = None
    group_by = []
    
    if "compare" in q_lower or " vs " in q_lower or "versus" in q_lower:
        intent = "compare"
        if "this month" in q_lower and "last month" in q_lower:
            selected_range = DateRange(start=dates["this_month"][0], end=dates["this_month"][1])
            compare_range = DateRange(start=dates["last_month"][0], end=dates["last_month"][1])
    elif "show me" in q_lower or "list" in q_lower or "top" in q_lower or "subscriptions" in q_lower:
        intent = "list"
        if "last 5" in q_lower or "top 5" in q_lower:
            limit = 5
        elif "last 10" in q_lower:
            limit = 10

    # Metric detection
    metric = "sum"
    if "how many" in q_lower or "count" in q_lower or "subscriptions" in q_lower:
        metric = "count"
    elif "average" in q_lower or "avg" in q_lower:
        metric = "avg"
    elif "biggest" in q_lower or "most" in q_lower or "max" in q_lower:
        metric = "max"

    # Category and merchant filters
    categories = []
    merchants = []
    
    if "food" in q_lower or "dining" in q_lower:
        categories.extend(["dining", "groceries"])
    elif "groceries" in q_lower:
        categories.append("groceries")
    elif "subscriptions" in q_lower:
        categories.append("subscriptions")
        group_by = ["merchant"]
    elif "transport" in q_lower:
        categories.append("transport")
    elif "shopping" in q_lower:
        categories.append("shopping")
    elif "entertainment" in q_lower:
        categories.append("entertainment")
    elif "travel" in q_lower:
        categories.append("travel")

    if "swiggy" in q_lower:
        merchants.append("swiggy")
    elif "amazon" in q_lower:
        merchants.append("amazon")
    elif "zomato" in q_lower:
        merchants.append("zomato")
    elif "netflix" in q_lower:
        merchants.append("netflix")
    elif "uber" in q_lower:
        merchants.append("uber")

    # Money movement vs spending
    exclude_transfers = not ("came into" in q_lower or "income" in q_lower or "credit" in q_lower)
    tx_type = "credit" if ("came into" in q_lower or "income" in q_lower) else "debit"

    return QueryIR(
        intent=intent,
        metric=metric,
        date_range=selected_range,
        compare_date_range=compare_range,
        filters=QueryFilters(
            category=categories,
            merchant=merchants,
            transaction_type=tx_type,
            exclude_transfers=exclude_transfers
        ),
        group_by=group_by,
        limit=limit
    )

def generate_ir(
    question: str,
    ref_date: Optional[date] = None,
    api_key: Optional[str] = None
) -> QueryIR:
    """
    Generates a QueryIR object from a natural language question.
    Uses OpenAI LLM API if key is present; otherwise uses deterministic rule fallback.
    """
    if ref_date is None:
        ref_date = date(2026, 8, 11)
        
    today_str = ref_date.strftime("%Y-%m-%d")
    key_to_use = api_key or OPENAI_API_KEY

    if not key_to_use:
        logger.info("OPENAI_API_KEY not configured. Using rule-based IR fallback generator.")
        return _rule_based_ir_fallback(question, ref_date)

    try:
        from openai import OpenAI
        client = OpenAI(api_key=key_to_use, base_url=OPENAI_BASE_URL or None)
        
        prompt_template = load_prompt("prompt1_nl_to_ir.txt")
        formatted_prompt = prompt_template.format(
            today=today_str,
            ir_schema=IR_SCHEMA_STRING
        )

        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": formatted_prompt},
                {"role": "user", "content": question}
            ],
            temperature=0.0,
            response_format={"type": "json_object"}
        )
        
        content = response.choices[0].message.content
        parsed_json = json.loads(content)
        return QueryIR.model_validate(parsed_json)
        
    except Exception as e:
        logger.warning(f"Stage 1 LLM generation failed ({e}), falling back to deterministic IR parser.")
        return _rule_based_ir_fallback(question, ref_date)
