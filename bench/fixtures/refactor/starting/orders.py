"""Order summaries (duplicated formatting logic)."""


def summarize_book(order):
    lines = [f"Order {order['id']}"]
    for item in order["items"]:
        lines.append(f"  {item['name']} x{item['qty']} @ ${item['price']:.2f}")
    lines.append(f"Subtotal: ${sum(i['qty'] * i['price'] for i in order['items']):.2f}")
    return "\n".join(lines)


def summarize_movie(order):
    lines = [f"Order {order['id']}"]
    for item in order["items"]:
        lines.append(f"  {item['name']} x{item['qty']} @ ${item['price']:.2f}")
    lines.append(f"Subtotal: ${sum(i['qty'] * i['price'] for i in order['items']):.2f}")
    return "\n".join(lines)
