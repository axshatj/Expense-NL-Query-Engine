"""
Stage 3 Grounded Response & Anti-Hallucination Guardrail:
Generates natural language answers strictly backed by query results with post-hoc verification.
"""
import re
import json
import logging
from typing import Dict, Any, List, Optional
from src.config import OPENAI_API_KEY, OPENAI_BASE_URL, LLM_MODEL
from src.prompts import load_prompt

logger = logging.getLogger(__name__)


def extract_all_numbers(data: Any) -> List[float]:
    """
    Recursively extracts all numeric values (integers, floats) from nested dictionaries, lists, or primitive types.
    """
    numbers: List[float] = []

    if isinstance(data, bool):
        return numbers
    elif isinstance(data, (int, float)):
        numbers.append(float(data))
    elif isinstance(data, dict):
        for key, value in data.items():
            numbers.extend(extract_all_numbers(value))
    elif isinstance(data, (list, tuple)):
        for item in data:
            numbers.extend(extract_all_numbers(item))
    elif isinstance(data, str):
        # Clean potential formatted money strings e.g. "₹12,450.50" or "12450.5"
        matches = re.findall(r"[\d,]+\.?\d*", data)
        for match in matches:
            cleaned = match.replace(",", "")
            if cleaned and cleaned != ".":
                try:
                    numbers.append(float(cleaned))
                except ValueError:
                    pass

    return numbers


def verify_grounded(answer: str, query_result: Dict[str, Any]) -> bool:
    """
    Verifies that every numeric figure in the generated natural language answer
    appears within the query_result data (within a rounding tolerance of 1.0).
    """
    # Extract raw candidate numbers from answer
    raw_matches = re.findall(r"[\d,]+\.?\d*", answer)
    numbers_in_answer: List[float] = []
    
    for match in raw_matches:
        cleaned = match.replace(",", "")
        if cleaned and cleaned != ".":
            try:
                val = float(cleaned)
                # Ignore isolated 1-2 digit integers that might be list indices or word numbers if reasonable
                numbers_in_answer.append(val)
            except ValueError:
                pass

    if not numbers_in_answer:
        return True

    numbers_in_data = extract_all_numbers(query_result)

    if not numbers_in_data:
        # If query_result has no numbers (e.g. empty list/0 result), answer shouldn't state positive figures
        return False

    for num in numbers_in_answer:
        # Check if num matches any number in query_result data within tolerance
        if not any(abs(num - d) < 1.0 for d in numbers_in_data):
            logger.warning(f"Anti-hallucination guardrail failed: number {num} in answer not found in data.")
            return False

    return True


def generate_templated_fallback(query_result: Dict[str, Any], question: str) -> str:
    """
    Generates a deterministic, guaranteed correct natural language response directly from query_result.
    """
    status = query_result.get("status")
    intent = query_result.get("intent")

    if status == "unrelated":
        return query_result.get(
            "message",
            "I am an expense tracking assistant. I can only answer questions related to your personal transactions."
        )

    if intent == "compare":
        p_res = query_result.get("primary_period", {}).get("result", 0.0)
        c_res = query_result.get("compare_period", {}).get("result", 0.0)
        p_val = f"₹{p_res:,.2f}" if isinstance(p_res, (int, float)) else str(p_res)
        c_val = f"₹{c_res:,.2f}" if isinstance(c_res, (int, float)) else str(c_res)
        return (
            f"For the primary period, your total was {p_val}, "
            f"compared to {c_val} in the comparison period."
        )

    if intent == "list":
        rows = query_result.get("data", [])
        count = query_result.get("count", len(rows))
        if count == 0 or not rows:
            return "No matching transactions were found for the requested period."
        
        tx_summaries = []
        for r in rows[:5]: # Cap at top 5 for prose summary
            merchant = r.get("merchant_normalized") or r.get("merchant_raw") or "Unknown Merchant"
            amt = r.get("amount", 0.0)
            dt = r.get("date", "")
            tx_summaries.append(f"{dt}: {merchant} (₹{amt:,.2f})")
            
        summary_str = "; ".join(tx_summaries)
        if count > 5:
            return f"Found {count} transactions (showing top 5): {summary_str}."
        return f"Found {count} transaction(s): {summary_str}."

    # Intent: aggregate or trend
    data = query_result.get("data")
    metric = query_result.get("metric", "sum")

    if isinstance(data, list):
        if not data:
            return "No data found matching your query."
        items = []
        for row in data:
            grp = [str(v) for k, v in row.items() if k != "result"]
            res = row.get("result", 0.0)
            grp_label = " / ".join(grp) if grp else "Total"
            val_str = f"₹{res:,.2f}" if metric != "count" else str(int(res))
            items.append(f"{grp_label}: {val_str}")
        return "Breakdown: " + ", ".join(items) + "."

    val = data if data is not None else 0.0
    if metric == "count":
        return f"Total count: {int(val)} matching transaction(s)."
    
    val_str = f"₹{val:,.2f}"
    return f"Your total {metric} spending for the requested period was {val_str}."


def generate_grounded_answer(
    question: str,
    query_result: Dict[str, Any],
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Generates a natural language answer grounded in query_result.
    Uses LLM with Prompt 2 when API key is available, verifies correctness via regex,
    and falls back to deterministic templated response on any failure.
    """
    if query_result.get("status") == "unrelated":
        return {
            "answer": query_result.get("message", "I am an expense tracking assistant."),
            "is_grounded": True,
            "fallback_used": False
        }

    key_to_use = api_key or OPENAI_API_KEY

    if not key_to_use:
        logger.info("OPENAI_API_KEY not configured. Generating deterministic templated answer.")
        fallback = generate_templated_fallback(query_result, question)
        return {
            "answer": fallback,
            "is_grounded": True,
            "fallback_used": True
        }

    try:
        from openai import OpenAI
        client = OpenAI(api_key=key_to_use, base_url=OPENAI_BASE_URL or None)

        prompt_template = load_prompt("prompt2_grounding.txt")
        formatted_prompt = prompt_template.format(
            query_result_json=json.dumps(query_result, indent=2),
            original_question=question
        )

        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": formatted_prompt},
                {"role": "user", "content": question}
            ],
            temperature=0.0
        )

        answer = response.choices[0].message.content.strip()
        is_grounded = verify_grounded(answer, query_result)

        if is_grounded:
            return {
                "answer": answer,
                "is_grounded": True,
                "fallback_used": False
            }
        else:
            logger.warning("LLM response failed numeric grounding check. Using templated fallback.")
            fallback = generate_templated_fallback(query_result, question)
            return {
                "answer": fallback,
                "is_grounded": False,
                "fallback_used": True
            }

    except Exception as e:
        logger.warning(f"Stage 3 LLM grounded response failed ({e}). Using templated fallback.")
        fallback = generate_templated_fallback(query_result, question)
        return {
            "answer": fallback,
            "is_grounded": False,
            "fallback_used": True
        }
