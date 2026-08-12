from datetime import date, timedelta
from typing import Dict, Tuple

def get_resolved_date_ranges(ref_date: date) -> Dict[str, Tuple[str, str]]:
    """
    Computes absolute YYYY-MM-DD start and end date ranges for common relative date phrases.
    """
    # 1. Today & Yesterday
    today_str = ref_date.strftime("%Y-%m-%d")
    yesterday_str = (ref_date - timedelta(days=1)).strftime("%Y-%m-%d")

    # 2. This Month: 1st of current month -> today
    this_month_start = ref_date.replace(day=1).strftime("%Y-%m-%d")

    # 3. Last Month: 1st of previous month -> last day of previous month
    first_of_this_month = ref_date.replace(day=1)
    last_day_prev_month = first_of_this_month - timedelta(days=1)
    first_day_prev_month = last_day_prev_month.replace(day=1)
    
    last_month_start = first_day_prev_month.strftime("%Y-%m-%d")
    last_month_end = last_day_prev_month.strftime("%Y-%m-%d")

    # 4. This Year: Jan 1st of current year -> today
    this_year_start = date(ref_date.year, 1, 1).strftime("%Y-%m-%d")

    # 5. Last N Days
    last_7_days_start = (ref_date - timedelta(days=7)).strftime("%Y-%m-%d")
    last_30_days_start = (ref_date - timedelta(days=30)).strftime("%Y-%m-%d")
    last_90_days_start = (ref_date - timedelta(days=90)).strftime("%Y-%m-%d")

    return {
        "today": (today_str, today_str),
        "yesterday": (yesterday_str, yesterday_str),
        "this_month": (this_month_start, today_str),
        "last_month": (last_month_start, last_month_end),
        "this_year": (this_year_start, today_str),
        "last_7_days": (last_7_days_start, today_str),
        "last_30_days": (last_30_days_start, today_str),
        "last_90_days": (last_90_days_start, today_str),
    }
