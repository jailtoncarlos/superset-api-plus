"""The AUTH_TYPE a Superset page declares in its bootstrap data: pure parsing of synthetic pages, no HTTP.

How the login behaves on a real instance (a password form, a refused password, an OAuth login page) is tested in
tests/integration/test_auth.py.
"""
import html
import json

from supersetapiplus.auth.session import page_auth_type


def page(conf: dict) -> str:
    bootstrap = html.escape(json.dumps({"user": {}, "common": {"conf": conf}}), quote=True)
    return f'<html><body><div id="app" data-bootstrap="{bootstrap}"></div>' \
           '<input type="hidden" name="csrf_token" value="t"/></body></html>'


def test_the_auth_type_comes_from_the_bootstrap_conf():
    assert page_auth_type(page({"AUTH_TYPE": 4, "AUTH_PROVIDERS": [{"name": "keycloak"}]})) == 4
    assert page_auth_type(page({"AUTH_TYPE": 1})) == 1


def test_a_page_without_bootstrap_or_auth_type_declares_none():
    assert page_auth_type("<form><input name='csrf_token' value='t'/></form>") is None
    assert page_auth_type(page({"AUTH_USER_REGISTRATION": False})) is None
    assert page_auth_type('<div data-bootstrap="not json"></div>') is None
