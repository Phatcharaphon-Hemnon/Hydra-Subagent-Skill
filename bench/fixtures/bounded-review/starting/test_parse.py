"""Frozen acceptance tests for the bounded-review fixture."""

import pytest

from parse import parse_port


def test_valid_port():
    assert parse_port(80) == 80
    assert parse_port("443") == 443


def test_rejects_non_integer():
    with pytest.raises(ValueError):
        parse_port("abc")


def test_rejects_negative():
    with pytest.raises(ValueError):
        parse_port(-1)


def test_rejects_out_of_range():
    with pytest.raises(ValueError):
        parse_port(70000)


def test_rejects_none():
    with pytest.raises(ValueError):
        parse_port(None)
