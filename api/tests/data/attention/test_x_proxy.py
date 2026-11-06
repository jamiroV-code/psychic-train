"""B2 pure security boundary regressions; no network or deployment ACL probing."""
from datetime import UTC, datetime
import pytest
from api.data.attention import x_proxy as p


def test_duplicate_json_never_accepts_last_value():
    with pytest.raises(p.ProxyFailure, match="proxy_config"):
        p.strict_json(b'{"version":1,"version":1}')


@pytest.mark.parametrize("url", ["http://example.com", "https://u:p@example.com", "https://example.com/a", "https://example.com?x=1", "https://example.com#x"])
def test_origins_reject_ambiguous_or_insecure_values(url):
    with pytest.raises(p.ProxyFailure):
        p.canonical_origin(url, origin_only=True)


def test_origin_normalization():
    assert p.canonical_origin("https://EXAMPLE.com:443/", origin_only=True) == "https://example.com"


@pytest.mark.parametrize("url", ["http://user:secret@proxy.example:80", "socks5://proxy.example", "http://proxy.example/path", "https://proxy.example?x=secret"])
def test_proxy_schemes_and_plaintext_auth_fail_closed(url):
    with pytest.raises(p.ProxyFailure) as result:
        p.parse_proxy(url)
    assert "secret" not in str(result.value)
    assert result.value.__cause__ is None


def test_https_proxy_credentials_not_represented():
    route = p.parse_proxy("https://user:secret@proxy.example:8443")
    assert route.url == "https://proxy.example:8443"
    assert route.auth == ("user", "secret")
    assert "secret" not in repr(route)


@pytest.mark.parametrize("ip", ["127.0.0.1", "10.0.0.1", "169.254.169.254", "::1", "224.0.0.1", "192.0.2.1"])
def test_production_address_rejection(ip):
    with pytest.raises(p.ProxyFailure, match="proxy_address"):
        p.public_address(ip)


def test_connect_rewrites_only_complete_validated_frame():
    frame = p.ConnectFrame({b"example.com:443": b"8.8.8.8:443"})
    assert frame.feed(b"CONNECT example.com:443 HTTP/1.1\r\nHo") is None
    assert frame.feed(b"st: example.com:443\r\n\r\n") == b"CONNECT 8.8.8.8:443 HTTP/1.1\r\nHost: 8.8.8.8:443\r\n\r\n"
    assert frame.feed(b"CONNECT untouched TLS application") == b"CONNECT untouched TLS application"


@pytest.mark.parametrize("frame", [b"GET / HTTP/1.1\r\nHost: example.com:443\r\n\r\n", b"CONNECT example.com:443 HTTP/1.1\r\nHost: example.com:443\r\nHost: example.com:443\r\n\r\n", b"CONNECT example.com:443 HTTP/1.1\r\nHost: example.com:443\r\nContent-Length: 0\r\n\r\n", b"CONNECT example.com:443 HTTP/1.1\r\nHost: example.com:443\r\n\r\nextra"])
def test_connect_ambiguity_rejected(frame):
    with pytest.raises(p.ProxyFailure):
        p.ConnectFrame({b"example.com:443": b"8.8.8.8:443"}).feed(frame)


def test_connect_header_bounded():
    with pytest.raises(p.ProxyFailure):
        p.ConnectFrame({}).feed(b"a" * 16385)


def test_failure_cannot_carry_arbitrary_reason():
    assert str(p.ProxyFailure("https://user:secret@proxy")) == "proxy_transport"
