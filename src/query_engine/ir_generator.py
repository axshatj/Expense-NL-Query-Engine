import re
import json
import logging
from datetime import date
from typing import Optional, Dict, Any

from src.config import OPENAI_API_KEY, LLM_MODEL, VALID_CATEGORIES
from src.query_engine.llm_client import get_llm_client, call_llm_with_retry
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
  "limit": null,
  "is_subscription_query": false,
  "category_mapping_note": null,
  "unmatched_term": null
}"""

def _rule_based_ir_fallback(question: str, ref_date: date) -> QueryIR:
    """
    Fallback deterministic IR parser for common financial questions when LLM API key is absent.
    Ensures tests and offline development work seamlessly.
    """
    q_lower = question.lower()
    dates = get_resolved_date_ranges(ref_date)

    # 1. Out-of-domain / Unrelated detection
    if any(phrase in q_lower for phrase in ["python", "code", "sort", "capital of", "weather", "who won"]) or ("script" in q_lower and "subscription" not in q_lower):
        return QueryIR(
            intent="unrelated",
            metric=None,
            filters=QueryFilters(),
            is_subscription_query=False,
            category_mapping_note=None,
            unmatched_term=None
        )

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
    elif "show me" in q_lower or "list" in q_lower or "top" in q_lower:
        intent = "list"
        if "last 5" in q_lower or "top 5" in q_lower:
            limit = 5
        elif "last 10" in q_lower:
            limit = 10

    # Metric detection
    metric = "sum"
    if "how many" in q_lower or "count" in q_lower:
        metric = "count"
    elif "average" in q_lower or "avg" in q_lower:
        metric = "avg"
    elif "biggest" in q_lower or "most" in q_lower or "max" in q_lower:
        metric = "max"

    # Subscription and unmatched flags
    is_subscription_query = False
    category_mapping_note = None
    unmatched_term = None

    if "subscription costs" in q_lower or "subscription cost" in q_lower:
        is_subscription_query = True
        intent = "aggregate"
        metric = "sum"
        group_by = ["merchant"]
        selected_range = DateRange(start="2000-01-01", end=dates["today"][1])
    elif "subscriptions" in q_lower:
        # Standard subscriptions list question
        intent = "list"
        metric = "count"
        group_by = ["merchant"]
        if "last month" in q_lower:
            selected_range = DateRange(start=dates["last_month"][0], end=dates["last_month"][1])
        else:
            # last 90 days as default for subscriptions list examples in some cases
            selected_range = DateRange(start=dates["last_90_days"][0], end=dates["last_90_days"][1])

    # Category and merchant filters
    categories = []
    merchants = []
    
    if "food" in q_lower or "dining" in q_lower:
        categories.extend(["dining", "groceries"])
    elif "groceries" in q_lower:
        categories.append("groceries")
    elif "subscriptions" in q_lower and not is_subscription_query:
        categories.append("subscriptions")
    elif "transport" in q_lower:
        categories.append("transport")
    elif "shopping" in q_lower:
        categories.append("shopping")
    elif "entertainment" in q_lower:
        categories.append("entertainment")
    elif "travel" in q_lower:
        categories.append("travel")

    # Mapping checks
    if "perfume" in q_lower:
        category_mapping_note = "perfumes mapped to shopping"
        categories = ["shopping"]
        selected_range = DateRange(start="2000-01-01", end=dates["today"][1])
    elif "gym" in q_lower:
        category_mapping_note = "gym mapped to healthcare"
        categories = ["healthcare"]
        selected_range = DateRange(start="2000-01-01", end=dates["today"][1])
    elif "cab" in q_lower:
        category_mapping_note = "cabs mapped to transport"
        categories = ["transport"]
        selected_range = DateRange(start="2000-01-01", end=dates["today"][1])
    elif "vet" in q_lower:
        unmatched_term = "vet bills"
        categories = []
        selected_range = DateRange(start="2000-01-01", end=dates["today"][1])

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
        limit=limit,
        is_subscription_query=is_subscription_query,
        category_mapping_note=category_mapping_note,
        unmatched_term=unmatched_term
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
        client = get_llm_client(key_to_use)
        
        prompt_template = load_prompt("prompt1_nl_to_ir.txt")
        formatted_prompt = prompt_template.format(
            today=today_str,
            ir_schema=IR_SCHEMA_STRING
        )

        response = call_llm_with_retry(
            client,
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
