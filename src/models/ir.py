from typing import Optional, List, Literal
from pydantic import BaseModel, Field

class DateRange(BaseModel):
    start: str  # YYYY-MM-DD
    end: str    # YYYY-MM-DD

class QueryFilters(BaseModel):
    category: Optional[List[str]] = Field(default_factory=list)
    merchant: Optional[List[str]] = Field(default_factory=list)
    transaction_type: Optional[Literal["debit", "credit"]] = "debit"
    amount_min: Optional[float] = None
    amount_max: Optional[float] = None
    exclude_transfers: bool = True

class QueryIR(BaseModel):
    intent: Literal["aggregate", "list", "compare", "trend", "unrelated"]
    metric: Optional[Literal["sum", "count", "avg", "max", "min"]] = "sum"
    date_range: Optional[DateRange] = None
    compare_date_range: Optional[DateRange] = None
    filters: QueryFilters = Field(default_factory=QueryFilters)
    group_by: List[str] = Field(default_factory=list)
    limit: Optional[int] = None
    is_subscription_query: bool = False
    category_mapping_note: Optional[str] = None
    unmatched_term: Optional[str] = None

