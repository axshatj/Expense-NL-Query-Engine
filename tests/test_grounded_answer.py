import pytest
from src.query_engine.grounded_answer import (
    extract_all_numbers,
    verify_grounded,
    generate_templated_fallback,
    generate_grounded_answer
)

def test_extract_all_numbers():
    """Verifies numeric extraction from nested data structures."""
    data = {
        "status": "success",
        "primary": {"result": 1250.50},
        "compare": {"result": 800.0},
        "items": [{"amount": 100}, {"amount": 200}]
    }
    extracted = extract_all_numbers(data)
    assert 1250.50 in extracted
    assert 800.0 in extracted
    assert 100.0 in extracted
    assert 200.0 in extracted

def test_verify_grounded_success():
    """Verifies grounding check passes when answer numbers exist in query data."""
    query_result = {
        "status": "success",
        "intent": "aggregate",
        "data": 1250.50
    }
    answer = "You spent ₹1,250.50 on dining last month."
    assert verify_grounded(answer, query_result) is True

def test_verify_grounded_hallucination():
    """Verifies anti-hallucination guardrail rejects answers with invented numbers."""
    query_result = {
        "status": "success",
        "intent": "aggregate",
        "data": 1250.50
    }
    answer = "You spent ₹5,432.10 on dining last month."
    assert verify_grounded(answer, query_result) is False

def test_generate_templated_fallback_aggregate():
    """Verifies templated fallback generation for aggregate intent."""
    query_result = {
        "status": "success",
        "intent": "aggregate",
        "metric": "sum",
        "data": 3450.75
    }
    fallback = generate_templated_fallback(query_result, "How much did I spend?")
    assert "₹3,450.75" in fallback

def test_generate_templated_fallback_compare():
    """Verifies templated fallback generation for compare intent."""
    query_result = {
        "status": "success",
        "intent": "compare",
        "metric": "sum",
        "primary_period": {"result": 1200.0},
        "compare_period": {"result": 800.0}
    }
    fallback = generate_templated_fallback(query_result, "Compare spending")
    assert "₹1,200.00" in fallback
    assert "₹800.00" in fallback

def test_generate_templated_fallback_list():
    """Verifies templated fallback generation for listing intent."""
    query_result = {
        "status": "success",
        "intent": "list",
        "count": 2,
        "data": [
            {"date": "2026-08-01", "merchant_normalized": "Swiggy", "amount": 350.0},
            {"date": "2026-08-05", "merchant_normalized": "Zomato", "amount": 420.0}
        ]
    }
    fallback = generate_templated_fallback(query_result, "Show transactions")
    assert "Swiggy" in fallback
    assert "₹350.00" in fallback
    assert "Zomato" in fallback

def test_generate_grounded_answer_offline(monkeypatch):
    """Verifies end-to-end grounded answer generation in offline/no-key mode."""
    monkeypatch.setattr("src.query_engine.grounded_answer.OPENAI_API_KEY", "")
    query_result = {
        "status": "success",
        "intent": "aggregate",
        "metric": "sum",
        "data": 1500.0
    }
    res = generate_grounded_answer("How much did I spend?", query_result)
    
    assert "answer" in res
    assert "₹1,500.00" in res["answer"]
    assert res["is_grounded"] is True
    assert res["fallback_used"] is True
