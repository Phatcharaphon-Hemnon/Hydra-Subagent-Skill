"""Acceptance tests for the small-fix fixture (currently failing)."""

from calc import total


def test_total_sums_values():
    assert total([1, 2, 3]) == 6


def test_total_empty():
    assert total([]) == 0
