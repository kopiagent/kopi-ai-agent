"""X-Forwarded-Prefix support on the server-rendered /login page.

Behind a path-prefix reverse proxy (Ingress at ``/i/<customer>`` →
dashboard :9119, header ``X-Forwarded-Prefix: /i/<customer>``), every
absolute URL the login page emits must carry the prefix — fonts, OAuth
provider hrefs, the password-login fetch target and the post-login
navigation. Regression guard for the KOPI per-customer path-routing
deploy (deploy/k8s/ingress-per-customer.yaml).
"""
from __future__ import annotations

import pytest

from kopi_cli.dashboard_auth import clear_providers, register_provider
from kopi_cli.dashboard_auth.login_page import render_login_html
from tests.kopi_cli.conftest_dashboard_auth import StubAuthProvider


class _PasswordStub(StubAuthProvider):
    """Stub provider that also offers a username/password form."""

    name = "pwstub"
    display_name = "Password Stub"
    supports_password = True


@pytest.fixture(autouse=True)
def _providers():
    clear_providers()
    yield
    clear_providers()


PREFIX = "/i/acme"


def test_oauth_login_page_prefixes_all_absolute_urls():
    register_provider(StubAuthProvider())
    html = render_login_html(prefix=PREFIX)
    # data-prefix 供内联脚本读取
    assert f'<html lang="en" data-prefix="{PREFIX}">' in html
    # 字体资源带前缀
    assert f"url('{PREFIX}/fonts/Collapse-Regular.woff2')" in html
    # OAuth 按钮 href 带前缀
    assert f'href="{PREFIX}/auth/login?provider=stub"' in html
    # 不残留未加前缀的绝对字体/登录 URL
    assert "url('/fonts/" not in html
    assert 'href="/auth/login' not in html


def test_root_serving_is_unchanged_without_prefix():
    register_provider(StubAuthProvider())
    html = render_login_html()
    assert '<html lang="en" data-prefix="">' in html
    assert "url('/fonts/Collapse-Regular.woff2')" in html
    assert 'href="/auth/login?provider=stub"' in html


def test_password_script_reads_prefix_and_prefixes_fetch():
    register_provider(_PasswordStub())
    html = render_login_html(prefix=PREFIX)
    # 脚本从 <html data-prefix> 读前缀
    assert "getAttribute('data-prefix')" in html
    # fetch 与登录成功后的跳转都拼上前缀
    assert "fetch(P + '/auth/password-login'" in html
    assert "window.location.assign(P + ((data && data.next) || '/'))" in html


def test_empty_providers_page_prefixes_fonts():
    html = render_login_html(prefix=PREFIX)
    assert f"url('{PREFIX}/fonts/" in html
    assert "url('/fonts/" not in html


def test_prefix_is_html_escaped_defence_in_depth():
    register_provider(StubAuthProvider())
    # normalise_prefix 拒绝引号/尖括号；这里验证纵深防御的转义不会破坏页面
    html = render_login_html(prefix='/i/a"b')
    assert 'data-prefix="/i/a&quot;b"' in html
