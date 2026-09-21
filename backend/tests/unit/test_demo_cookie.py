from types import SimpleNamespace

from fastapi import Response

from app.api.demo import demo_cookie_options


def request_from(origin):
    return SimpleNamespace(headers={"origin": origin} if origin else {})


def test_https_frontend_gets_a_cross_site_cookie():
    assert demo_cookie_options(request_from("https://draft-wise-gold.vercel.app")) == {
        "samesite": "none",
        "secure": True,
    }


def test_local_http_frontend_keeps_a_lax_cookie():
    assert demo_cookie_options(request_from("http://localhost:3000")) == {
        "samesite": "lax",
        "secure": False,
    }
    assert demo_cookie_options(request_from(None)) == {"samesite": "lax", "secure": False}


def test_cross_site_cookie_header_is_secure_and_http_only():
    response = Response()
    response.set_cookie(
        "draftwise_demo",
        "token",
        httponly=True,
        path="/api/v1",
        **demo_cookie_options(request_from("https://draft-wise-gold.vercel.app")),
    )
    header = response.headers["set-cookie"]
    assert "HttpOnly" in header
    assert "Secure" in header
    assert "SameSite=none" in header
