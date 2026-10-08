# refactor fixture

## Request

`summarize_book` and `summarize_movie` in `orders.py` are line-for-line
duplicates. Extract the shared logic into one private helper used by both,
without changing any observable output.

## Acceptance

- Both existing tests pass unchanged.
- Only one copy of the item-line format string remains in `orders.py`.
- `bash checks.sh /path/to/work/copy` exits 0.
