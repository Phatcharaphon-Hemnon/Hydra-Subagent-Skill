"""Behavior-preservation tests for the refactor fixture."""

from orders import summarize_book, summarize_movie

ORDER = {"id": 7, "items": [{"name": " pen ".strip(), "qty": 2, "price": 1.5}]}

EXPECTED = "Order 7\n  pen x2 @ $1.50\nSubtotal: $3.00"


def test_book_summary():
    assert summarize_book(ORDER) == EXPECTED


def test_movie_summary():
    assert summarize_movie(ORDER) == EXPECTED
