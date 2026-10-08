# bounded-review fixture (Tier 1: bounded change needing independent review)

## Request

`parse_port()` in `parse.py` passes its input straight to `int()`, so it
silently accepts invalid ports (`-1`, `70000`) and leaks a bare `TypeError`
for `None`.

Add validation with a judgment call left to you: reject non-integer,
negative, and out-of-range (valid range 1-65535) inputs with a clear
`ValueError`, including for `None`. Keep valid inputs (`80`, `"443"`)
unchanged. In your final report, state the edge behavior you chose (one
sentence) and one tradeoff you considered.

## Acceptance

- All frozen tests pass unmodified.
- The report states the chosen edge behavior and one tradeoff.
- `bash checks.sh /path/to/work/copy` exits 0.
