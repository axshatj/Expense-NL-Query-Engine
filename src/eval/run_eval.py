"""
Evaluation Runner: Evaluates the complete 3-stage NL Query Engine against benchmark.json.
Reports 3 core metrics: IR Field Accuracy, Numeric Accuracy, and Hallucination/Fallback Rate.
"""
import sys
import json
import logging
from pathlib import Path
from datetime import date
from typing import Dict, Any, List, Optional, Tuple

from src.query_engine.pipeline import answer_question
from src.query_engine.grounded_answer import extract_all_numbers

BENCHMARK_PATH = Path(__file__).parent / "benchmark.json"

logger = logging.getLogger(__name__)


def clean_text(text: str) -> str:
    """Replaces unprintable unicode characters for safe Windows console output."""
    return text.replace("₹", "Rs.").encode("ascii", errors="replace").decode("ascii")


def evaluate_ir_match(generated_ir: Dict[str, Any], expected_ir: Dict[str, Any]) -> Tuple[int, int]:
    """
    Compares generated_ir against expected_ir for specified fields.
    Returns (matched_fields, total_fields).
    """
    total = 0
    matched = 0

    for key, expected_val in expected_ir.items():
        if key == "filters" and isinstance(expected_val, dict):
            gen_filters = generated_ir.get("filters", {})
            for f_key, f_val in expected_val.items():
                total += 1
                gen_val = gen_filters.get(f_key)
                if isinstance(f_val, list):
                    if set(f_val).issubset(set(gen_val or [])):
                        matched += 1
                elif gen_val == f_val:
                    matched += 1
        else:
            total += 1
            gen_val = generated_ir.get(key)
            if isinstance(expected_val, list):
                if set(expected_val).issubset(set(gen_val or [])):
                    matched += 1
            elif gen_val == expected_val:
                matched += 1

    return matched, total


def evaluate_numeric_match(answer: str, expected_numbers: List[float], is_unrelated: bool) -> bool:
    """
    Checks if numbers in answer match expected ground-truth numbers within 1.0 tolerance.
    """
    if is_unrelated:
        return "expense tracking assistant" in answer or "personal transactions" in answer

    if not expected_numbers:
        return True

    answer_numbers = extract_all_numbers(answer)
    if not answer_numbers:
        return False

    # Check if at least one generated number matches an expected ground-truth number
    for ans_num in answer_numbers:
        for exp_num in expected_numbers:
            if abs(ans_num - exp_num) < 1.0:
                return True

    return False


def evaluate_question_fidelity(
    answer: str,
    expected_mapping: Optional[str],
    expected_unmatched: Optional[str]
) -> bool:
    """
    Checks if the answer correctly handles category-mapping disclosure
    or unmatched term refusal.
    """
    answer_lower = answer.lower()
    
    if expected_mapping:
        try:
            term, category = expected_mapping.split(" mapped to ")
            return term.lower() in answer_lower and category.lower() in answer_lower
        except Exception:
            return expected_mapping.lower() in answer_lower

    if expected_unmatched:
        return (
            "categorized under" in answer_lower
            and expected_unmatched.lower() in answer_lower
        )
        
    return True


def run_evaluation(
    ref_date: Optional[date] = None,
    db_path: Optional[str] = None,
    api_key: Optional[str] = None,
    benchmark_file: Path = BENCHMARK_PATH
) -> Dict[str, Any]:
    """
    Runs the full evaluation benchmark suite and prints comprehensive metrics report.
    """
    if ref_date is None:
        ref_date = date(2026, 8, 11)

    with open(benchmark_file, "r", encoding="utf-8") as f:
        benchmark_items = json.load(f)

    total_ir_matched = 0
    total_ir_checked = 0
    numeric_correct_count = 0
    fallback_count = 0
    fidelity_questions_count = 0
    fidelity_correct_count = 0
    total_questions = len(benchmark_items)

    detailed_results = []

    print(f"\n=======================================================")
    print(f" EXPENSE RAG ENGINE - EVALUATION BENCHMARK SUITE ({total_questions} Questions)")
    print(f"=======================================================\n")

    for item in benchmark_items:
        q_id = item["id"]
        question = item["question"]
        expected_ir = item.get("expected_ir", {})
        expected_numbers = item.get("expected_answer_contains", [])
        expected_mapping = item.get("expected_category_mapping_note")
        expected_unmatched = item.get("expected_unmatched_term")
        is_unrelated = expected_ir.get("intent") == "unrelated"

        res = answer_question(question, ref_date=ref_date, api_key=api_key, db_path=db_path)
        gen_ir = res["ir"]
        answer = res["answer"]
        fallback = res.get("fallback_used", False)

        # 1. IR Field Match
        matched, checked = evaluate_ir_match(gen_ir, expected_ir)
        total_ir_matched += matched
        total_ir_checked += checked
        ir_pct = (matched / checked * 100) if checked > 0 else 100.0

        # 2. Numeric Match
        num_ok = evaluate_numeric_match(answer, expected_numbers, is_unrelated)
        if num_ok:
            numeric_correct_count += 1

        # 3. Fallback tracking
        if fallback:
            fallback_count += 1

        # 4. Question Fidelity Match
        is_fidelity_q = bool(expected_mapping or expected_unmatched)
        fidelity_ok = True
        if is_fidelity_q:
            fidelity_questions_count += 1
            fidelity_ok = evaluate_question_fidelity(answer, expected_mapping, expected_unmatched)
            if fidelity_ok:
                fidelity_correct_count += 1

        status_str = "PASS" if (ir_pct == 100 and num_ok and (not is_fidelity_q or fidelity_ok)) else "FAIL"
        clean_q = clean_text(question)
        clean_ans = clean_text(answer)
        
        print(f"[{status_str}] Q{q_id:02d}: \"{clean_q}\"")
        print(f"     IR Accuracy: {ir_pct:.0f}% ({matched}/{checked} fields)")
        print(f"     Answer: \"{clean_ans[:80]}...\"" if len(clean_ans) > 80 else f"     Answer: \"{clean_ans}\"")
        print(f"     Numeric Grounding: {'PASS' if num_ok else 'FAIL'} | Fallback Used: {fallback}")
        if is_fidelity_q:
            print(f"     Question Fidelity: {'PASS' if fidelity_ok else 'FAIL'}")
        print()

        detailed_results.append({
            "id": q_id,
            "question": question,
            "ir_accuracy_pct": ir_pct,
            "numeric_ok": num_ok,
            "fallback_used": fallback,
            "fidelity_ok": fidelity_ok if is_fidelity_q else None,
            "answer": answer
        })

    ir_field_accuracy = (total_ir_matched / total_ir_checked * 100) if total_ir_checked > 0 else 0.0
    numeric_accuracy = (numeric_correct_count / total_questions * 100) if total_questions > 0 else 0.0
    hallucination_fallback_rate = (fallback_count / total_questions * 100) if total_questions > 0 else 0.0
    question_fidelity_rate = (fidelity_correct_count / fidelity_questions_count * 100) if fidelity_questions_count > 0 else 100.0

    summary = {
        "total_questions": total_questions,
        "ir_field_accuracy_pct": round(ir_field_accuracy, 2),
        "numeric_accuracy_pct": round(numeric_accuracy, 2),
        "hallucination_fallback_rate_pct": round(hallucination_fallback_rate, 2),
        "question_fidelity_rate_pct": round(question_fidelity_rate, 2),
        "detailed_results": detailed_results
    }

    print(f"=======================================================")
    print(f" EVALUATION BENCHMARK SUMMARY METRICS")
    print(f"=======================================================")
    print(f" 1. IR Field Accuracy:        {ir_field_accuracy:.2f}%")
    print(f" 2. Numeric Accuracy:         {numeric_accuracy:.2f}%")
    print(f" 3. Hallucination/Fallback:   {hallucination_fallback_rate:.2f}%")
    print(f" 4. Question Fidelity Rate:   {question_fidelity_rate:.2f}%")
    print(f"=======================================================\n")

    return summary



if __name__ == "__main__":
    run_evaluation()
