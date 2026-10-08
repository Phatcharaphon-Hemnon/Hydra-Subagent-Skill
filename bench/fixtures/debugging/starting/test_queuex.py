"""Regression tests for the debugging fixture (currently failing)."""

from queuex import run_queue


def test_all_jobs_complete():
    assert run_queue(["a", "b", "c"]) == ["a-done", "b-done", "c-done"]


def test_single_job():
    assert run_queue(["only"]) == ["only-done"]


def test_empty_queue():
    assert run_queue([]) == []
