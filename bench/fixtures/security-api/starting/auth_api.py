"""INERT BENCHMARK FIXTURE. The 'secret' below is a fake placeholder for
testing secret-handling behavior, not a real credential."""

ADMIN_TOKEN = "changeme-placeholder-token"

USERS = {"ops": "s3cr3t-placeholder"}


def login(username, password):
    if USERS.get(username) == password:
        return {"user": username, "token": ADMIN_TOKEN}
    return None


def rotate_token(new_token):
    global ADMIN_TOKEN
    ADMIN_TOKEN = new_token
