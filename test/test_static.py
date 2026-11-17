from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


def test_serve_index():
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Local Voice Assistant" in response.text


def test_serve_static_assets():
    css_res = client.get("/static/style.css")
    assert css_res.status_code == 200

    js_res = client.get("/static/app.js")
    assert js_res.status_code == 200

    marked_res = client.get("/static/marked.min.js")
    assert marked_res.status_code == 200

