"""
Compute Ground Truth: Evaluates benchmark questions against SQLite database snapshot
and updates benchmark.json with ground-truth expected numbers.
"""
import json
from pathlib import Path
from datetime import date
from typing import Optional, Dict, Any, List

from src.query_engine.ir_generator import generate_ir
from src.query_engine.db_executor import execute_ir
from src.query_engine.grounded_answer import extract_all_numbers

BENCHMARK_PATH = Path(__file__).parent / "benchmark.json"


def compute_ground_truth_for_item(
    item: Dict[str, Any],
    ref_date: date,
    db_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Computes ground-truth numeric expectations for a single benchmark item.
    """
    question = item["question"]
    ir = generate_ir(question, ref_date=ref_date)
    db_res = execute_ir(ir, db_path=db_path)
    
    numbers = extract_all_numbers(db_res)
    item["expected_answer_contains"] = list(set(numbers))
    return item


def compute_all_ground_truth(
    ref_date: Optional[date] = None,
    db_path: Optional[str] = None,
    benchmark_file: Path = BENCHMARK_PATH
) -> List[Dict[str, Any]]:
    """
    Computes ground truth for all benchmark items and writes back to benchmark.json.
    """
    if ref_date is None:
        ref_date = date(2026, 8, 11)

    with open(benchmark_file, "r", encoding="utf-8") as f:
        items = json.load(f)

    updated_items = []
    for item in items:
        updated = compute_ground_truth_for_item(item, ref_date=ref_date, db_path=db_path)
        updated_items.append(updated)

    with open(benchmark_file, "w", encoding="utf-8") as f:
        json.dump(updated_items, f, indent=2)

    return updated_items


if __name__ == "__main__":
    compute_all_ground_truth()
    print("Successfully updated benchmark.json ground truth numeric expectations!")
