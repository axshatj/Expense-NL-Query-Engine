import pytest
from datetime import date
from src.models.ir import QueryIR, DateRange, QueryFilters
from src.query_engine.date_resolver import get_resolved_date_ranges
from src.query_engine.ir_generator import generate_ir

@pytest.fixture(autouse=True)
def disable_api(monkeypatch):
    monkeypatch.setattr("src.query_engine.ir_generator.OPENAI_API_KEY", "")

def test_query_ir_model_validation():
    """Verifies Pydantic QueryIR model validation and default values."""
    ir_data = {
        "intent": "aggregate",
        "metric": "sum",
        "date_range": {"start": "2026-07-01", "end": "2026-07-31"},
        "filters": {"category": ["dining"], "transaction_type": "debit", "exclude_transfers": True}
    }
    ir = QueryIR.model_validate(ir_data)
    assert ir.intent == "aggregate"
    assert ir.metric == "sum"
    assert ir.date_range.start == "2026-07-01"
    assert ir.filters.category == ["dining"]
    assert ir.filters.exclude_transfers is True

def test_date_resolver():
    """Verifies calculation of relative date ranges."""
    ref = date(2026, 8, 11)
    dates = get_resolved_date_ranges(ref)
    
    assert dates["today"] == ("2026-08-11", "2026-08-11")
    assert dates["this_month"] == ("2026-08-01", "2026-08-11")
    assert dates["last_month"] == ("2026-07-01", "2026-07-31")
    assert dates["this_year"] == ("2026-01-01", "2026-08-11")

def test_generate_ir_aggregate():
    """Tests generating IR for aggregate dining expense question."""
    ref = date(2026, 8, 11)
    ir = generate_ir("How much did I spend on food last month?", ref_date=ref)
    
    assert ir.intent == "aggregate"
    assert ir.metric == "sum"
    assert ir.date_range.start == "2026-07-01"
    assert ir.date_range.end == "2026-07-31"
    assert "dining" in ir.filters.category

def test_generate_ir_compare():
    """Tests generating IR for comparison question."""
    ref = date(2026, 8, 11)
    ir = generate_ir("Compare my spending this month vs last month", ref_date=ref)
    
    assert ir.intent == "compare"
    assert ir.date_range.start == "2026-08-01"
    assert ir.compare_date_range.start == "2026-07-01"

def test_generate_ir_list():
    """Tests generating IR for transaction listing question."""
    ref = date(2026, 8, 11)
    ir = generate_ir("Show me my last 5 transactions at Swiggy", ref_date=ref)
    
    assert ir.intent == "list"
    assert ir.limit == 5
    assert "swiggy" in ir.filters.merchant

def test_generate_ir_unrelated():
    """Tests that out-of-domain coding/trivia question generates intent='unrelated'."""
    ref = date(2026, 8, 11)
    ir = generate_ir("Write a Python script to sort a list of numbers", ref_date=ref)
    
    assert ir.intent == "unrelated"
