"""Cross-module consistency tests (currently failing)."""

from pricing import price_after_discount
from receipt import format_receipt


def test_receipt_matches_pricing():
    assert format_receipt(100) == "Total: $90.00"
    assert price_after_discount(100) == 90.0
