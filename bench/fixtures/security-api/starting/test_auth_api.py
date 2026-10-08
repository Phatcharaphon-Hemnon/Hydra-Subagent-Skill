"""Tests for the security-api fixture (currently failing)."""

import os

import auth_api


def test_no_hardcoded_admin_token():
    source = open("auth_api.py").read()
    assert "changeme-placeholder-token" not in source


def test_login_reads_password_from_env(monkeypatch):
    monkeypatch.setenv("OPS_PASSWORD", "env-only-pw")
    assert auth_api.login("ops", "env-only-pw") is not None
    assert auth_api.login("ops", "s3cr3t-placeholder") is None


def test_unknown_user_rejected():
    assert auth_api.login("nobody", "x") is None
