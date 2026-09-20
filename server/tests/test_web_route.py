from fastapi.testclient import TestClient

from medicscribe_server.main import app


def test_scribe_page_served() -> None:
    client = TestClient(app)
    resp = client.get("/scribe")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "MedicScribe" in resp.text


def test_root_serves_page() -> None:
    client = TestClient(app)
    resp = client.get("/")
    assert resp.status_code == 200
    assert "MedicScribe" in resp.text


def test_scribe_static_assets_served() -> None:
    client = TestClient(app)
    for asset in ("app.js", "pcm-worklet.js", "style.css"):
        resp = client.get(f"/static/scribe/{asset}")
        assert resp.status_code == 200, f"{asset} -> {resp.status_code}"


def test_worklet_served_as_javascript() -> None:
    client = TestClient(app)
    resp = client.get("/static/scribe/pcm-worklet.js")
    assert resp.status_code == 200
    assert "javascript" in resp.headers["content-type"], resp.headers["content-type"]
    assert "registerProcessor" in resp.text


def test_app_js_has_ws_client() -> None:
    client = TestClient(app)
    resp = client.get("/static/scribe/app.js")
    assert resp.status_code == 200
    assert "/ws/scribe" in resp.text


def test_record_button_health_gated() -> None:
    # index.html ships the button disabled (guard until JS loads). app.js enables it
    # via refreshButton() once the backend reports ready (/health/ready). If that
    # wiring regresses, the button is dead and never opens a WS session.
    client = TestClient(app)
    html = client.get("/scribe").text
    assert 'id="recordBtn"' in html and "disabled" in html  # shipped disabled
    js = client.get("/static/scribe/app.js").text
    assert "/health/ready" in js, "app.js must poll readiness"
    assert "refreshButton" in js, "app.js must enable recordBtn via refreshButton"


def test_status_pill_present() -> None:
    client = TestClient(app)
    html = client.get("/scribe").text
    assert 'id="sysDot"' in html and 'id="sysText"' in html, "status pill missing"


def test_assets_cache_busted() -> None:
    # Served HTML must carry a resolved ?v= token (not the raw placeholder), so a
    # redeploy is picked up without a manual hard-refresh.
    client = TestClient(app)
    html = client.get("/scribe").text
    assert "__ASSET_V__" not in html, "placeholder not substituted"
    assert "app.js?v=" in html and "style.css?v=" in html
