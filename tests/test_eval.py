import pytest
from datetime import date
from src.eval.run_eval import evaluate_ir_match, evaluate_numeric_match, run_evaluation
from src.eval.compute_ground_truth import compute_ground_truth_for_item
from src.db.connection import get_db_connection, init_db
from src.ingestion.synthetic import generate_synthetic_transactions

def test_evaluate_ir_match():
    """Verifies IR field matching percentage calculation."""
    expected_ir = {
        "intent": "aggregate",
        "metric": "sum",
        "filters": {"category": ["dining"], "transaction_type": "debit"}
    }
    gen_ir = {
        "intent": "aggregate",
        "metric": "sum",
        "filters": {"category": ["dining", "groceries"], "transaction_type": "debit"}
    }
    matched, total = evaluate_ir_match(gen_ir, expected_ir)
    assert matched == 4
    assert total == 4

def test_evaluate_numeric_match():
    """Verifies numeric matching check against expected ground-truth numbers."""
    answer = "You spent ₹1,250.00 on dining last month."
    expected_numbers = [1250.0, 500.0]
    assert evaluate_numeric_match(answer, expected_numbers, is_unrelated=False) is True

def test_evaluate_numeric_match_unrelated():
    """Verifies refusal text check for out-of-domain questions."""
    answer = "I am an expense tracking assistant. I can only answer questions related to your transactions."
    assert evaluate_numeric_match(answer, [], is_unrelated=True) is True

def test_compute_ground_truth_item(tmp_path):
    """Verifies computing ground truth for a single benchmark item."""
    db_file = str(tmp_path / "test_eval_gt.db")
    conn = get_db_connection(db_file)
    init_db(conn=conn)
    
    txs = generate_synthetic_transactions(count=20, start_date=date(2026, 1, 1), end_date=date(2026, 8, 11), seed=50)
    cursor = conn.cursor()
    cursor.executemany(
        """
        INSERT INTO transactions (date, amount, transaction_type, merchant_raw, merchant_normalized, category, source, account_id, currency, raw_text)
        VALUES (:date, :amount, :transaction_type, :merchant_raw, :merchant_normalized, :category, :source, :account_id, :currency, :raw_text)
        """,
        txs
    )
    conn.commit()
    conn.close()

    item = {
        "id": 1,
        "question": "How much did I spend on food last month?",
        "expected_ir": {"intent": "aggregate", "metric": "sum"}
    }

    updated = compute_ground_truth_for_item(item, ref_date=date(2026, 8, 11), db_path=db_file)
    assert "expected_answer_contains" in updated
    assert isinstance(updated["expected_answer_contains"], list)
