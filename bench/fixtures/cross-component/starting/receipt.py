"""Receipt module: formats the total shown to the customer."""

DISCOUNT_RATE = 0.15


def format_receipt(amount):
    total = amount * (1 - DISCOUNT_RATE)
    return f"Total: ${total:.2f}"
