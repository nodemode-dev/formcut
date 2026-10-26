"""F1, the family guard contract (FAMILY_TEST_PLAN layer F1), fed by formcut's own origin list.

LocalOnly answers a foreign Host, a foreign or null Origin, and a cross-site request with no
Origin with 403; the window's own origins pass. Writes also need the x-formcut-local header, so
the refusal cases send it and the verdict is the Origin's alone. A refused websocket closes 1008
here (the family template says 4403). Websocket requests carry an explicit loopback Host header.
"""

import pytest
from app.main import app
from app.security import DEV_ORIGINS
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

PORT = 8123
OWN = f"http://127.0.0.1:{PORT}"
HEALTH = "/api/health"
WS = "/api/rpc/ws"
WINDOW_ORIGINS = [*DEV_ORIGINS, "tauri://localhost", "http://tauri.localhost"]
FOREIGN_ORIGINS = [
    "http://evil.example",
    "https://evil.example",
    f"http://localhost.evil.com:{PORT}",
    f"http://127.0.0.1.evil.com:{PORT}",
    "http://localhost:3099",
    "http://127.0.0.1:3099",
    "null",
    "file://",
]
FOREIGN_HOSTS = ["evil.example", f"evil.example:{PORT}", f"localhost.evil.com:{PORT}", f"192.168.1.10:{PORT}"]
LOCAL = {"x-formcut-local": "1"}


@pytest.fixture(scope="module")
def client():
    return TestClient(app, base_url=OWN)


def test_foreign_origins_are_not_in_the_apps_own_list():
    assert not set(FOREIGN_ORIGINS) & set(WINDOW_ORIGINS)


@pytest.mark.parametrize("host", FOREIGN_HOSTS)
def test_foreign_host_is_refused(client, host):
    assert client.get(HEALTH, headers={"host": host}).status_code == 403


@pytest.mark.parametrize("origin", FOREIGN_ORIGINS)
def test_foreign_origin_is_refused(client, origin):
    assert client.get(HEALTH, headers={"origin": origin}).status_code == 403


@pytest.mark.parametrize("origin", FOREIGN_ORIGINS)
def test_foreign_origin_cannot_write(client, origin):
    assert client.post("/api/rpc", headers={"origin": origin, **LOCAL}, json={}).status_code == 403


def test_a_write_needs_the_local_header_even_from_the_own_origin(client):
    assert client.post("/api/rpc", headers={"origin": OWN}, json={}).status_code == 403
    assert client.post("/api/rpc", headers={"origin": OWN, **LOCAL}, json={}).status_code != 403


def test_cross_site_request_without_origin_is_refused(client):
    assert client.get(HEALTH, headers={"sec-fetch-site": "cross-site"}).status_code == 403


@pytest.mark.parametrize("value", ["CROSS-SITE", " cross-site "])
def test_cross_site_marker_is_read_loosely(client, value):
    assert client.get(HEALTH, headers={"sec-fetch-site": value}).status_code == 403


@pytest.mark.parametrize("origin", [OWN, *WINDOW_ORIGINS])
def test_allowed_origin_passes(client, origin):
    assert client.get(HEALTH, headers={"origin": origin}).status_code == 200


@pytest.mark.parametrize("host", [f"localhost:{PORT}", f"[::1]:{PORT}"])
def test_own_origin_under_another_loopback_name_passes(client, host):
    assert client.get(HEALTH, headers={"host": host, "origin": f"http://{host}"}).status_code == 200


def test_own_origin_must_match_the_host_it_was_sent_to(client):
    assert client.get(HEALTH, headers={"host": f"127.0.0.1:{PORT}", "origin": f"http://127.0.0.1:{PORT + 1}"}).status_code == 403


@pytest.mark.parametrize("site", ["same-origin", "same-site", "none"])
def test_browser_request_without_origin_passes_unless_cross_site(client, site):
    assert client.get(HEALTH, headers={"sec-fetch-site": site}).status_code == 200


def test_plain_client_without_origin_passes(client):
    assert client.get(HEALTH).status_code == 200


@pytest.mark.parametrize("host", [f"127.0.0.1:{PORT}", f"localhost:{PORT}", f"[::1]:{PORT}"])
def test_loopback_hosts_pass(client, host):
    assert client.get(HEALTH, headers={"host": host}).status_code == 200


@pytest.mark.parametrize(
    "headers",
    [
        {"host": "evil.example"},
        {"host": f"127.0.0.1:{PORT}", "origin": "http://evil.example"},
        {"host": f"127.0.0.1:{PORT}", "origin": "http://localhost:3099"},
        {"host": f"127.0.0.1:{PORT}", "origin": "null"},
    ],
)
def test_foreign_websocket_is_closed_1008(client, headers):
    with pytest.raises(WebSocketDisconnect) as refused, client.websocket_connect(WS, headers=headers) as ws:
        ws.send_json({"jsonrpc": "2.0", "id": 1, "method": "no.such.method"})
        ws.receive_json()
    assert refused.value.code == 1008


def test_websocket_from_the_own_origin_is_accepted(client):
    with client.websocket_connect(WS, headers={"host": f"127.0.0.1:{PORT}", "origin": OWN}) as ws:
        ws.send_json({"jsonrpc": "2.0", "id": 1, "method": "no.such.method"})
        assert ws.receive_json()["id"] == 1
