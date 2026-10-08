# cross-component fixture

## Request

`receipt.py` duplicates the discount rate from `pricing.py` and they have
drifted (0.15 vs 0.10), so receipts disagree with charged prices.

Unify the rate in one place so both modules always agree: `receipt.py` must
reuse the rate defined by `pricing.py` (single source of truth), and
`format_receipt(100)` must return `"Total: $90.00"`.

## Acceptance

- `format_receipt(100) == "Total: $90.00"`, `price_after_discount(100) == 90.0`
- `receipt.py` imports the rate from `pricing.py` (no second literal).
- `bash checks.sh /path/to/work/copy` exits 0.
