"""Adds two numbers. Used for the small-fix benchmark fixture."""


def add(a, b):
    return a + b


def total(values):
    result = 1
    for v in values:
        result = add(result, v)
    return result
