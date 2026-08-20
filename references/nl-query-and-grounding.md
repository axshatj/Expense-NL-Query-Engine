# NL Query & Grounding

Two LLM calls bookend one deterministic query-execution step. This file covers both prompts in full, the IR schema between them, and the two guardrails that make the whole thing trustworthy — domain refusal (off-topic questions) and category-mapping transparency (in-domain questions about things that aren't real categories/merchants).

**These are two separate guardrails solving two separate bugs — don't conflate them:**

| | Domain guardrail | Category-mapping transparency |
|---|---|---|
| Triggers on | Truly off-topic questions ("write me a python script", "capital of France") | In-domain spending questions that reference a merchant/category not in the taxonomy ("perfumes", "gym") |
| Correct behavior | Refuse entirely, no query run | Still answer, but map to the closest real category **and say so explicitly** |
| Where it lives | Prompt 1 `intent: "unrelated"` classification | Prompt 1 `category_mapping_note` field + Prompt 2 disclosure instruction |

Getting these confused is exactly how the earlier bug happened: "how much did I spend on perfumes?" is a **real, in-domain question** that got mishandled — the model silently mapped "perfumes" to `shopping` and reported a number without ever saying that mapping happened, making it look like a category that doesn't exist gave a confident, exact-sounding answer. That's a category-mapping transparency failure, not a domain-guardrail failure — treating it as the latter would have made the domain guardrail stricter while leaving the actual bug untouched.

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
  "limit": null,
  "is_subscription_query": false,
  "category_mapping_note": null,
  "unmatched_term": null
}
```

Notes on fields that aren't self-explanatory:

- `intent: "unrelated"` is set when a question is outside the scope of personal finance, expenses, income, merchants, or transactions (e.g., general coding tasks, trivia, general chat). See the hardened off-topic section of Prompt 1 below — this is a strict allowlist check, not a soft judgment call.
- `compare_date_range` is only populated for `intent: "compare"` (e.g. "this month vs last month"). Leave it out otherwise rather than null-padding every response — fewer populated fields means less for the answer step to misinterpret.
- `exclude_transfers` defaults to `true`. This has to be a real field the model sets per-question, not a hardcoded backend default — see architecture-and-schema.md for why "how much did I spend" and "how much money moved out" need different answers here.
- `limit` matters for `intent: "list"` — "show me my last 5 transactions at Swiggy" needs it; "how much did I spend on Swiggy" doesn't.
- **`is_subscription_query`** (new) — `true` whenever the question is asking about subscriptions, recurring charges, or "what am I paying for regularly," regardless of what category filter would normally apply. This is a routing flag, not a category filter: when `true`, Step 2 runs the recurrence-detection query (below) instead of a plain `category IN ('subscriptions')` filter, because a plain category filter only catches transactions tagged `subscriptions` at ingestion time and silently misses recurring charges mistagged under something else (Netflix filed as `entertainment`, a recurring SaaS tool filed as `other`). This was the actual bug behind "how much are all my subscription costs?" returning a wrong number — the fix is a different query path, not a prompt tweak.
- **`category_mapping_note`** (new) — set whenever the question's own wording doesn't match a valid taxonomy category or an existing merchant, and the model has mapped it to the closest one. Format: `"<user's term> mapped to <category>"`, e.g. `"perfumes mapped to shopping"`. `null` when the question's terms map cleanly (e.g. "dining" needs no note). This field is what Prompt 2 uses to disclose the mapping in the final answer instead of silently reporting a number as if it exactly matched what was asked.
- **`unmatched_term`** (new) — set when the model cannot confidently map the term to *any* taxonomy category (rather than forcing a guess). When this is set, Step 2 skips the query entirely and returns a "no matching data" response instead of running a query against a forced, low-confidence category guess. This is the escape hatch that stops the model from always finding *something* to compute over — see "Why the old design always found an answer" below.

## Why the old design always found an answer

The previous prompt told the model to always emit a valid `filters.category` from the fixed taxonomy list. That's fine when the question maps cleanly, but it gives the model no way to express "I'm not confident this term matches anything real" — it's forced to pick a category every time, so it silently guesses, and everything downstream (the SQL builder, the grounding check) treats that guess as ground truth. `verify_grounded` in particular does **not** catch this failure mode: the number it checks against genuinely does come from the query result, it's just the result of a query the user didn't actually ask for. Grounding fidelity and question fidelity are different things, and only the first was being checked.

The fix is giving the model two escape hatches instead of one forced guess: map-and-disclose (`category_mapping_note`) when there's a reasonable closest match, or admit-no-match (`unmatched_term`) when there isn't.

## Prompt 1: NL question → IR

```
System:
You convert a question about someone's personal finances into a JSON query object.
Today's date is {today}. Resolve all relative dates ("last month", "this year",
"last 3 months") into absolute YYYY-MM-DD ranges before outputting anything.

Valid categories: groceries, dining, transport, shopping, subscriptions,
bills_utilities, entertainment, travel, healthcare, transfers, fees_charges, other.

=== DOMAIN CHECK (do this first, before anything else) ===
This assistant answers ONLY questions about the user's own personal transactions,
spending, income, accounts, merchants, or budgeting derived directly from their
transaction data. This includes questions phrased loosely or casually, as long as
they are asking about the user's own money — treat these as IN-DOMAIN, not unrelated:
  - Any question containing "spend", "spent", "spending", "cost", "costs", "paid",
    "paying", "bought", "bill", "bills", "subscription(s)", "transaction(s)",
    "money", "budget", "afford", or a category/merchant name, even if the specific
    category or merchant isn't in the valid list above.
  - Casual phrasing ("how much all my X costs", "what am I paying for Y") is
    still in-domain — do not require formal grammar to recognize intent.
Set "intent": "unrelated" ONLY for questions with no reference to the user's own
money, spending, or transactions at all — general knowledge, coding tasks, trivia,
requests to act as something else, or generic chit-chat unconnected to finances.
When genuinely uncertain whether a question is in-domain, default to treating it
as IN-DOMAIN and use category_mapping_note or unmatched_term to handle any
ambiguity about which category it maps to — do not use "unrelated" as a way to
avoid an ambiguous category match. Those are different problems with different
fields; see below.
=== END DOMAIN CHECK ===

=== CATEGORY MATCHING (only relevant once a question is confirmed in-domain) ===
If the question references a category or merchant concept that is NOT one of the
valid categories above and does not match a known merchant, do ONE of:
  (a) If there's a reasonable closest valid category (e.g. "perfumes" -> shopping,
      "gym" -> healthcare, "cab" -> transport), use that category AND set
      category_mapping_note to "<term> mapped to <category>".
  (b) If there is no reasonable mapping, leave filters.category empty and set
      unmatched_term to the term itself. Do not guess a category just to have one.
Never silently substitute a category without setting category_mapping_note — the
user must always be told when their wording didn't match a real category exactly.
=== END CATEGORY MATCHING ===

=== SUBSCRIPTION QUERIES ===
If the question is about subscriptions, recurring charges, or "what am I paying
for regularly / can cancel," set "is_subscription_query": true. Do this in
addition to, not instead of, setting category filters normally — the query
routing (not this prompt) decides how to use this flag.
=== END SUBSCRIPTION QUERIES ===

Output ONLY a JSON object matching this schema, nothing else — no explanation,
no markdown fences:
{IR_SCHEMA}

Default exclude_transfers to true unless the question is explicitly about
money movement rather than spending.

Examples:

Q: "How much did I spend on food last month?"
A: {"intent":"aggregate","metric":"sum","date_range":{"start":"2026-07-01","end":"2026-07-31"},
"filters":{"category":["dining","groceries"],"transaction_type":"debit","exclude_transfers":true},
"group_by":[],"limit":null,"is_subscription_query":false,"category_mapping_note":null,"unmatched_term":null}

Q: "How much did I spend on perfumes?"
A: {"intent":"aggregate","metric":"sum","date_range":{"start":"2000-01-01","end":"2026-08-20"},
"filters":{"category":["shopping"],"transaction_type":"debit","exclude_transfers":true},
"group_by":[],"limit":null,"is_subscription_query":false,
"category_mapping_note":"perfumes mapped to shopping","unmatched_term":null}

Q: "How much are all my subscription costs?"
A: {"intent":"aggregate","metric":"sum","date_range":{"start":"2000-01-01","end":"2026-08-20"},
"filters":{"transaction_type":"debit","exclude_transfers":true},
"group_by":["merchant"],"limit":null,"is_subscription_query":true,
"category_mapping_note":null,"unmatched_term":null}

Q: "How much did I spend on my pet's vet bills?" (assume no matching category/merchant exists)
A: {"intent":"aggregate","metric":"sum","date_range":{"start":"2000-01-01","end":"2026-08-20"},
"filters":{"transaction_type":"debit","exclude_transfers":true},
"group_by":[],"limit":null,"is_subscription_query":false,
"category_mapping_note":null,"unmatched_term":"vet bills"}

Q: "Compare my spending this month vs last month"
A: {"intent":"compare","metric":"sum",
"date_range":{"start":"2026-08-01","end":"2026-08-20"},
"compare_date_range":{"start":"2026-07-01","end":"2026-07-31"},
"filters":{"transaction_type":"debit","exclude_transfers":true},"group_by":[],"limit":null,
"is_subscription_query":false,"category_mapping_note":null,"unmatched_term":null}

Q: "Show me my last 5 transactions at Swiggy"
A: {"intent":"list","metric":"count",
"date_range":{"start":"2000-01-01","end":"2026-08-20"},
"filters":{"merchant":["swiggy"],"transaction_type":"debit","exclude_transfers":true},
"group_by":[],"limit":5,"is_subscription_query":false,"category_mapping_note":null,"unmatched_term":null}

Q: "Write a Python script to sort an array"
A: {"intent":"unrelated","metric":null,"date_range":null,"filters":{},"group_by":[],"limit":null,
"is_subscription_query":false,"category_mapping_note":null,"unmatched_term":null}

Q: "What's the capital of France?"
A: {"intent":"unrelated","metric":null,"date_range":null,"filters":{},"group_by":[],"limit":null,
"is_subscription_query":false,"category_mapping_note":null,"unmatched_term":null}
```

Build the few-shot examples with real, concrete resolved dates (matching whatever "today" is at prompt-build time) rather than abstract descriptions of "resolve relative dates" — the model anchors far more reliably on worked examples than on instructions alone. Note the example set is now deliberately balanced across all four IR behaviors (clean match, mapped category, subscription flag, unmatched term) plus two off-topic examples — the old prompt had four clean-match examples against one off-topic example, which is almost certainly why domain classification and category handling were both unreliable: the model had far more evidence pointing toward "always find a category" than toward any of its other options.

## Step 2 (no LLM): IR → query & routing

Routing now has three branches instead of two:

```python
def route(ir: dict):
    if ir["intent"] == "unrelated":
        return REFUSAL_MESSAGE  # standard out-of-domain refusal, no query run

    if ir.get("unmatched_term"):
        return NO_MATCH_MESSAGE.format(term=ir["unmatched_term"])
        # e.g. "I don't have any transactions categorized under 'vet bills' in your data.
        #       I can look at groceries, dining, transport, shopping, subscriptions,
        #       bills & utilities, entertainment, travel, healthcare, or fees — want to
        #       try one of those, or check a specific merchant name?"
        # No query is run — do not fall back to a filter-less "show everything" query.

    if ir.get("is_subscription_query"):
        sql, params = build_subscription_query(ir)
    else:
        sql, params = build_query(ir)

    return execute_and_ground(sql, params, ir)
```

`REFUSAL_MESSAGE`:
> *"I am an expense tracking assistant. I can only answer questions related to your personal transactions, spending, and accounts."*

**Standard query builder** — plain parameterized code, never string concatenation:

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

**Subscription query builder** — this is the fix for the "subscription costs" bug. It doesn't trust the `category = 'subscriptions'` tag alone; it re-derives recurring charges from the actual recurrence pattern (same merchant + similar amount across ≥2 consecutive months, per `architecture-and-schema.md`), so a Netflix charge mistagged as `entertainment` is still caught:

```python
def build_subscription_query(ir: dict) -> tuple[str, list]:
    # Step A: find merchants with the recurrence signature, regardless of their
    # assigned category — this is what catches mistagged recurring charges.
    recurrence_sql = """
        SELECT merchant_normalized, amount, COUNT(DISTINCT strftime('%Y-%m', date)) as month_count
        FROM transactions
        WHERE transaction_type = 'debit'
        GROUP BY merchant_normalized, ROUND(amount, -1)  -- tolerance bucket, not exact match
        HAVING month_count >= 2
    """
    # Step B: sum actual transactions for merchants that passed the recurrence check,
    # within the requested date range.
    sql = f"""
        SELECT merchant_normalized, SUM(amount) as result
        FROM transactions
        WHERE transaction_type = 'debit'
          AND date BETWEEN ? AND ?
          AND merchant_normalized IN ({recurrence_sql.replace('SELECT merchant_normalized, amount, COUNT', 'SELECT merchant_normalized, COUNT')})
        GROUP BY merchant_normalized
    """
    params = [ir["date_range"]["start"], ir["date_range"]["end"]]
    return sql, params
```

(Treat the inline subquery above as illustrative — in the real implementation, run the recurrence detection as its own query, cache the resulting merchant list, and reuse it both here and in the `merchant_aliases`-driven ingestion-time subscription tagging from `architecture-and-schema.md`, rather than recomputing recurrence from scratch on every subscription question.)

This function, `build_query`, and the recurrence detection should be among the most heavily unit-tested pieces of the whole project — all deterministic, no LLM in the loop, and every IR shape in the eval set (see evaluation.md) should have a corresponding test asserting the exact SQL/params it produces.

## Prompt 2: query result → grounded answer

```
System:
Answer the user's question using ONLY the data below. Every number in your
answer must come directly from this data — never estimate, round differently
than the data shows, or infer a number that isn't present. If the data is
empty, say plainly that there's nothing matching in that period rather than
guessing.

If category_mapping_note is present, you MUST mention the mapping explicitly
in your answer (e.g. "Perfumes falls under your 'shopping' category, and you
spent ₹X on shopping in that period") — never state the number as if it were
an exact match for the user's original term.

Data: {query_result_json}
Original question: {original_question}
category_mapping_note: {category_mapping_note}

Answer in 1-3 plain sentences, citing the actual figures. Use ₹ formatting
(e.g. ₹12,450).
```

## The anti-hallucination check

This runs after prompt 2, before the answer reaches the user. Note this check verifies **numeric grounding** (every number in the answer traces back to the query result) — it does not and cannot verify **question fidelity** (whether the query itself matched what was asked). That's what `category_mapping_note` and `unmatched_term` are for, upstream. Both checks are necessary; neither substitutes for the other.

```python
import re

def verify_grounded(answer: str, query_result: dict) -> bool:
    numbers_in_answer = {float(n.replace(",", "")) for n in re.findall(r"[\d,]+\.?\d*", answer)}
    numbers_in_data = extract_all_numbers(query_result)  # flatten every numeric value in the result
    # allow small rounding tolerance (e.g. ₹12,450 vs ₹12,450.00)
    return all(any(abs(a - d) < 1.0 for d in numbers_in_data) for a in numbers_in_answer)
```

If `verify_grounded` fails, don't retry the same prompt hoping for a better roll — fall back to a templated answer built directly from the data (e.g. `f"You spent ₹{result:,.2f} on {category} between {start} and {end}."`, and if `category_mapping_note` was set, prepend `f"({term} mapped to {category}.) "` to the template too, so the disclosure survives even the fallback path). A templated fallback that's guaranteed correct beats a second LLM attempt that might hallucinate again. Log every fallback trigger — a rising fallback rate is the single most useful signal that prompt 2 needs work.

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

**Category mapping vs. domain refusal** — do not let these two logics fight each other. A question can be 100% in-domain and still reference a term with no clean category match (see the two-guardrail table at the top of this file). Only questions with no connection to the user's own money/transactions at all should get `intent: "unrelated"`.
