"""Pricing module: computes a discounted price."""

DISCOUNT_RATE = 0.10


def price_after_discount(amount):
    return amount * (1 - DISCOUNT_RATE)
