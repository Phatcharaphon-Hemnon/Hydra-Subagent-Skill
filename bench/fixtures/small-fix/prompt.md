# small-fix fixture

Fix the narrow bug described below. This is a Tier 0 candidate: authorized,
low-risk, clear acceptance, no cross-component impact.

## Request

`total()` in `calc.py` returns wrong results: `total([1, 2, 3])` gives 7
instead of 6, and `total([])` gives 1 instead of 0.

Fix the bug with the smallest correct change. Do not refactor anything else.
