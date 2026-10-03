"""Rate limiter client-key derivation — defends against proxy-header spoofing.

earth-monitor runs on Render behind Cloudflare. X-Forwarded-For's rightmost
hop on that path is Cloudflare's own edge IP, not the real client — keying
on it would put every caller in one shared bucket (a useless limiter: one
heavy client exhausts the cap for everyone). Cloudflare sets CF-Connecting-IP
(and, for some configurations, True-Client-IP) to the real client IP, so the
limiter keys on those instead and never trusts X-Forwarded-For. With no
proxy in front (local dev), it falls back to the socket address.
"""

from starlette.requests import Request

from app.api.ratelimit import _client_key


def _request(
    client_host: str,
    *,
    xff: str | None = None,
    cf_connecting_ip: str | None = None,
    true_client_ip: str | None = None,
) -> Request:
    headers = []
    if xff:
        headers.append((b"x-forwarded-for", xff.encode()))
    if cf_connecting_ip:
        headers.append((b"cf-connecting-ip", cf_connecting_ip.encode()))
    if true_client_ip:
        headers.append((b"true-client-ip", true_client_ip.encode()))
    scope = {"type": "http", "headers": headers, "client": (client_host, 51234)}
    return Request(scope)


def test_client_key_prefers_cf_connecting_ip_over_any_xff() -> None:
    # the old rightmost-XFF behavior would key this on "9.9.9.9" (the edge
    # hop Cloudflare appends) instead of the real client in CF-Connecting-IP
    # — this assertion fails under that behavior.
    req = _request(client_host="10.0.0.1", xff="1.2.3.4, 9.9.9.9", cf_connecting_ip="203.0.113.7")
    assert _client_key(req) == "203.0.113.7"


def test_client_key_prefers_cf_connecting_ip_over_spoofed_xff() -> None:
    a = _request(client_host="10.0.0.1", xff="10.0.0.1, 9.9.9.9", cf_connecting_ip="203.0.113.7")
    b = _request(client_host="10.0.0.2", xff="10.0.0.2, 9.9.9.9", cf_connecting_ip="203.0.113.7")
    assert _client_key(a) == _client_key(b) == "203.0.113.7"


def test_client_key_uses_true_client_ip_when_cf_connecting_ip_absent() -> None:
    req = _request(client_host="10.0.0.1", xff="1.2.3.4, 9.9.9.9", true_client_ip="203.0.113.9")
    assert _client_key(req) == "203.0.113.9"


def test_client_key_distinguishes_different_cf_connecting_ips() -> None:
    a = _request(client_host="10.0.0.1", cf_connecting_ip="203.0.113.7")
    b = _request(client_host="10.0.0.1", cf_connecting_ip="203.0.113.8")
    assert _client_key(a) != _client_key(b)


def test_client_key_falls_back_to_socket_without_proxy_headers() -> None:
    assert _client_key(_request(client_host="127.0.0.1")) == "127.0.0.1"


def test_client_key_ignores_xff_entirely_without_cloudflare_headers() -> None:
    # no CF-Connecting-IP / True-Client-IP at all: must not fall back to XFF
    assert _client_key(_request(client_host="127.0.0.1", xff="1.2.3.4, 9.9.9.9")) == "127.0.0.1"
