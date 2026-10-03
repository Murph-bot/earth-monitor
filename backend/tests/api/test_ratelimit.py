"""Rate limiter client-key derivation — defends against X-Forwarded-For spoofing.

Render's proxy appends the real client IP as the last hop of X-Forwarded-For;
earlier hops are whatever the caller sent. With FORWARDED_ALLOW_IPS="*",
uvicorn's ProxyHeadersMiddleware sets request.client to the *leftmost* XFF
hop — attacker-controlled — so keying the limiter on request.client.host
alone lets a caller rotate that hop to get a fresh bucket on every request
(see earth-monitor review, bug 1). The fix keys on the rightmost hop of the
raw header instead, falling back to the socket address when there is no
proxy in front (local dev).
"""

from starlette.requests import Request

from app.api.ratelimit import _client_key


def _request(client_host: str, xff: str | None) -> Request:
    headers = [(b"x-forwarded-for", xff.encode())] if xff else []
    scope = {"type": "http", "headers": headers, "client": (client_host, 51234)}
    return Request(scope)


def test_client_key_uses_rightmost_xff_hop_not_spoofable_leftmost() -> None:
    # simulates what uvicorn sets request.client to once FORWARDED_ALLOW_IPS
    # trusts the proxy: the caller-controlled leftmost hop. Two requests with
    # different attacker-chosen leftmost hops but the same real (rightmost,
    # proxy-appended) IP must land in the same bucket.
    a = _request(client_host="10.0.0.1", xff="10.0.0.1, 9.9.9.9")
    b = _request(client_host="10.0.0.2", xff="10.0.0.2, 9.9.9.9")
    assert _client_key(a) == _client_key(b) == "9.9.9.9"


def test_client_key_distinguishes_different_real_clients() -> None:
    a = _request(client_host="10.0.0.1", xff="10.0.0.1, 9.9.9.9")
    b = _request(client_host="10.0.0.1", xff="10.0.0.1, 8.8.8.8")
    assert _client_key(a) != _client_key(b)


def test_client_key_falls_back_to_socket_without_proxy() -> None:
    assert _client_key(_request(client_host="127.0.0.1", xff=None)) == "127.0.0.1"
