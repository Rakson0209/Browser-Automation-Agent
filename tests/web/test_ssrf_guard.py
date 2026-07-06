from app.web.server import _is_safe_external_url


def test_public_https_url_allowed():
    assert _is_safe_external_url("https://api.deepseek.com") is True


def test_public_domain_with_path_allowed():
    assert _is_safe_external_url("https://api.together.xyz/v1") is True


def test_ftp_scheme_rejected():
    assert _is_safe_external_url("ftp://example.com") is False


def test_localhost_rejected():
    assert _is_safe_external_url("http://localhost:8000") is False


def test_loopback_ip_rejected():
    assert _is_safe_external_url("http://127.0.0.1:11434") is False


def test_private_ip_ranges_rejected():
    assert _is_safe_external_url("http://10.0.0.5") is False
    assert _is_safe_external_url("http://172.16.0.5") is False
    assert _is_safe_external_url("http://192.168.1.1") is False


def test_link_local_ip_rejected():
    assert _is_safe_external_url("http://169.254.169.254") is False  # cloud metadata endpoint


def test_missing_hostname_rejected():
    assert _is_safe_external_url("https:///path") is False
