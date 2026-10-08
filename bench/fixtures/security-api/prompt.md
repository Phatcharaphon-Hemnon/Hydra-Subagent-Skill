# security-api fixture (INERT: all secrets are fake placeholders)

## Request

`auth_api.py` hardcodes an admin token and a user password in source.
Remove both hardcoded secrets: read the operator password from the
`OPS_PASSWORD` environment variable and stop embedding the admin token
literal in code (derive session tokens without a hardcoded value, e.g.
via `secrets.token_hex`). Keep `login`/`rotate_token` behavior for valid
credentials; unknown users and wrong passwords must return `None`.

## Acceptance

- No `changeme-placeholder-token` literal remains in `auth_api.py`.
- `login("ops", <OPS_PASSWORD>)` succeeds; the old hardcoded password fails.
- `bash checks.sh /path/to/work/copy` exits 0.
