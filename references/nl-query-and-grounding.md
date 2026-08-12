# NL Query & Grounding

Two LLM calls bookend one deterministic query-execution step. This file covers both prompts in full, the IR schema between them, and the guardrail that makes the whole thing trustworthy.

## The structured query IR (intermediate representation)

This is the *only* thing the first LLM call is allowed to produce. Nothing else — no SQL, no prose, no explanation.

```json
{
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
}
```

Notes on fields that aren't self-explanatory:

- `intent: "unrelated"` is set when a question is outside the scope of personal finance, expenses, income, merchants, or transactions (e.g., general coding tasks, trivia, general chat).
- `compare_date_range` is only populated for `intent: "compare"` (e.g. "this month vs last month"). Leave it out otherwise rather than null-padding every response — fewer populated fields means less for the answer step to misinterpret.
- `exclude_transfers` defaults to `true`. This has to be a real field the model sets per-question, not a hardcoded backend default — see architecture-and-schema.md for why "how much did I spend" and "how much money moved out" need different answers here.
- `limit` matters for `intent: "list"` — "show me my last 5 transactions at Swiggy" needs it; "how much did I spend on Swiggy" doesn't.

## Prompt 1: NL question → IR

```
System:
You convert a question about someone's personal finances into a JSON query object.
Today's date is {today}. Resolve all relative dates ("last month", "this year",
"last 3 months") into absolute YYYY-MM-DD ranges before outputting anything.

Valid categories: groceries, dining, transport, shopping, subscriptions,
bills_utilities, entertainment, travel, healthcare, transfers, fees_charges, other.

If the question is unrelated to personal finances, spending, income, merchants,
or transactions (e.g. general knowledge, writing code, off-topic chat), set
"intent": "unrelated".

Output ONLY a JSON object matching this schema, nothing else — no explanation,
no markdown fences:
{IR_SCHEMA}

Default exclude_transfers to true unless the question is explicitly about
money movement rather than spending.

Examples:

Q: "How much did I spend on food last month?"
A: {"intent":"aggregate","metric":"sum","date_range":{"start":"2026-07-01","end":"2026-07-31"},
"filters":{"category":["dining","groceries"],"transaction_type":"debit","exclude_transfers":true},
"group_by":[],"limit":null}

Q: "Compare my spending this month vs last month"
A: {"intent":"compare","metric":"sum",
"date_range":{"start":"2026-08-01","end":"2026-08-11"},
"compare_date_range":{"start":"2026-07-01","end":"2026-07-31"},
"filters":{"transaction_type":"debit","exclude_transfers":true},"group_by":[],"limit":null}

Q: "Show me my last 5 transactions at Swiggy"
A: {"intent":"list","metric":"count",
"date_range":{"start":"2000-01-01","end":"2026-08-11"},
"filters":{"merchant":["swiggy"],"transaction_type":"debit","exclude_transfers":true},
"group_by":[],"limit":5}

Q: "What subscriptions am I paying for?"
A: {"intent":"list","metric":"count",
"date_range":{"start":"2026-05-11","end":"2026-08-11"},
"filters":{"category":["subscriptions"],"transaction_type":"debit","exclude_transfers":true},
"group_by":["merchant"],"limit":null}

Q: "Write a Python script to sort an array"
A: {"intent":"unrelated","metric":null,"date_range":null,"filters":{},"group_by":[],"limit":null}
```

Build the few-shot examples with real, concrete resolved dates (matching whatever "today" is at prompt-build time) rather than abstract descriptions of "resolve relative dates" — the model anchors far more reliably on worked examples than on instructions alone.

## Step 2 (no LLM): IR → query & routing

If `ir["intent"] == "unrelated"`, bypass SQL query generation and Prompt 2 completely. Immediately return the standard out-of-domain refusal:
> *"I am an expense tracking assistant. I can only answer questions related to your personal transactions, spending, and accounts."*

Otherwise, build the SQL query via plain parameterized code, never string concatenation:

Plain parameterized code, never string concatenation:

```python
def build_query(ir: dict) -> tuple[str, list]:
    where = ["transaction_type = ?"]
    params = [ir["filters"]["transaction_type"]]

    where.append("date BETWEEN ? AND ?")
    params += [ir["date_range"]["start"], ir["date_range"]["end"]]

    if ir["filters"].get("exclude_transfers", True):
        where.append("category != 'transfers'")

    if ir["filters"].get("category"):
        placeholders = ",".join("?" * len(ir["filters"]["category"]))
        where.append(f"category IN ({placeholders})")
        params += ir["filters"]["category"]

    if ir["filters"].get("merchant"):
        # normalized merchant match, case-insensitive substring
        merchant_clauses = " OR ".join(["merchant_normalized LIKE ?"] * len(ir["filters"]["merchant"]))
        where.append(f"({merchant_clauses})")
        params += [f"%{m}%" for m in ir["filters"]["merchant"]]

    metric_sql = {
        "sum": "SUM(amount)", "count": "COUNT(*)", "avg": "AVG(amount)",
        "max": "MAX(amount)", "min": "MIN(amount)",
    }[ir["metric"]]

    group_clause = f"GROUP BY {', '.join(ir['group_by'])}" if ir["group_by"] else ""
    limit_clause = f"LIMIT {int(ir['limit'])}" if ir.get("limit") else ""

    select = f"{metric_sql} as result" if ir["intent"] != "list" else "*"
    sql = f"SELECT {select} FROM transactions WHERE {' AND '.join(where)} {group_clause} {limit_clause}"
    return sql, params
```

This function should be one of the most heavily unit-tested pieces of the whole project — it's deterministic, has no LLM in the loop, and every IR shape in the eval set (see evaluation.md) should have a corresponding test asserting the exact SQL/params it produces.

## Prompt 2: query result → grounded answer

```
System:
Answer the user's question using ONLY the data below. Every number in your
answer must come directly from this data — never estimate, round differently
than the data shows, or infer a number that isn't present. If the data is
empty, say plainly that there's nothing matching in that period rather than
guessing.

Data: {query_result_json}
Original question: {original_question}

Answer in 1-3 plain sentences, citing the actual figures. Use ₹ formatting
(e.g. ₹12,450).
```

## The anti-hallucination check

This runs after prompt 2, before the answer reaches the user:

```python
import re

def verify_grounded(answer: str, query_result: dict) -> bool:
    numbers_in_answer = {float(n.replace(",", "")) for n in re.findall(r"[\d,]+\.?\d*", answer)}
    numbers_in_data = extract_all_numbers(query_result)  # flatten every numeric value in the result
    # allow small rounding tolerance (e.g. ₹12,450 vs ₹12,450.00)
    return all(any(abs(a - d) < 1.0 for d in numbers_in_data) for a in numbers_in_answer)
```

If `verify_grounded` fails, don't retry the same prompt hoping for a better roll — fall back to a templated answer built directly from the data (e.g. `f"You spent ₹{result:,.2f} on {category} between {start} and {end}."`). A templated fallback that's guaranteed correct beats a second LLM attempt that might hallucinate again. Log every fallback trigger — a rising fallback rate is the single most useful signal that prompt 2 needs work.

## Ambiguity handling

**Relative dates** — resolve before the IR is used, not inside the SQL:

| Phrase | Resolves to |
|---|---|
| "this month" | 1st of current month → today |
| "last month" | full previous calendar month |
| "this year" | 1st Jan of current year → today |
| "last N days" | today − N days → today |
| "last quarter" | full previous calendar quarter |

**Merchant fuzzy matching** — `merchant_normalized LIKE '%swiggy%'` handles most cases since normalization already collapsed variants (see architecture-and-schema.md). For anything normalization missed, that's a signal to add a new `merchant_aliases` row, not to make the query layer fuzzier — keep the matching logic dumb and push intelligence into the alias table, where it's reusable and inspectable.