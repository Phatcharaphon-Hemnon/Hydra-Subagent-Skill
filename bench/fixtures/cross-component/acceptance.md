# cross-component acceptance

- `format_receipt(100) == "Total: $90.00"`
- `price_after_discount(100) == 90.0`
- `receipt.py` contains no numeric discount literal of its own.
- `bash checks.sh /path/to/work/copy` exits 0 (pytest plus literal check).
