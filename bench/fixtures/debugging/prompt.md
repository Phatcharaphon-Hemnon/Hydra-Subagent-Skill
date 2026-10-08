# debugging fixture

## Request

Jobs are silently dropped: `run_queue(["a", "b", "c"])` returns only
`["a-done", "b-done"]`, and a single-job queue returns `[]`.

Diagnose the root cause in `queuex.py`, fix it with the smallest correct
change, and report the cause in one sentence. Do not rewrite the module.

## Acceptance

- All three tests pass; report states the root cause (off-by-one bound).
- `bash checks.sh /path/to/work/copy` exits 0.
