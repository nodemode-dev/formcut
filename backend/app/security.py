import hmac
import ipaddress
import os
from urllib.parse import parse_qs, urlsplit

from starlette.responses import PlainTextResponse, RedirectResponse

from . import agent_access, remote, window_key


def loopback(value: str) -> bool:
    if value in ("localhost", "testclient", "testserver"):
        return True
    try:
        return ipaddress.ip_address(value).is_loopback
    except ValueError:
        return False


DEV_ORIGINS = (
    "http://localhost:3040",
    "http://127.0.0.1:3040",
    "http://localhost:3041",
    "http://127.0.0.1:3041",
)


def _origin_key(value: str) -> tuple[str, str, int | None] | None:
    try:
        parts = urlsplit(value.strip())
        port = parts.port
    except ValueError:
        return None
    if not parts.scheme or not parts.hostname:
        return None
    if port is None:
        port = {"http": 80, "https": 443}.get(parts.scheme)
    return parts.scheme.lower(), parts.hostname.lower(), port


def window_origin(origin: str, host: str) -> bool:
    key = _origin_key(origin)
    if key is None:
        return False
    if key in {k for k in (_origin_key(o) for o in [*DEV_ORIGINS, "tauri://localhost", "http://tauri.localhost"]) if k is not None}:
        return True
    own = _origin_key(f"{key[0]}://{host}")
    return key[0] == "http" and own is not None and own == key


READS = ("GET", "HEAD", "OPTIONS")
# Writes that answer without the window key: the development bootstrap, and the
# outside-agent door, which asks the person (agent_access.py) before it gives a pass.
OPEN = ("/api/window/key", "/api/agent-access/request", "/api/agent-access/pass", "/api/rpc/read")
# Neither an agent pass nor a paired device reaches these: only the window.
WINDOW_ONLY = ("/api/agent-access", "/api/window/", "/api/extensions/agent/", "/api/terminal/", "/api/agents/", "/api/remote")
# Reads that hand out the window's pending requests.
KEYED_READS = (
    "/api/extensions/agent/next",
    "/api/agent-access/waiting",
    "/api/agent-access/events",
    "/api/terminal/tabs",
    "/api/terminal/agents",
)


def _without_key(scope, headers: dict, through_network: bool) -> bool:
    """Whether a request that carries no window key may still go on."""
    path = scope.get("path", "")
    if scope["type"] == "websocket":
        ticket = parse_qs(scope.get("query_string", b"").decode("latin-1")).get("ticket", [""])[0]
        return window_key.spend(ticket)
    if path in KEYED_READS:
        return False
    if scope.get("method") in READS or path in OPEN:
        return True
    if through_network and path == "/api/remote/pair":
        return True
    if path.startswith(WINDOW_ONLY):
        return False
    if through_network or (remote_token() and hmac.compare_digest(headers.get("x-formcut-token", "").encode(), remote_token().encode())):
        return True
    return agent_access.pass_valid(headers.get(agent_access.PASS_HEADER))


def remote_token() -> str:
    """The token that allows non-loopback access; empty means remote is off."""
    return os.environ.get("FORMCUT_REMOTE_TOKEN", "").strip()


class LocalOnly:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket"):
            return await self.app(scope, receive, send)
        headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
        client = (scope.get("client") or ("",))[0]
        through_network = bool(scope.get("formcut.remote"))
        try:
            if through_network:
                # The network listener, marked by its own server: only paired
                # devices, and the pairing page, get through.
                allowed = remote.admitted(scope, headers)
            else:
                host = urlsplit("http://" + headers.get("host", "")).hostname or ""
                origin = headers.get("origin")
                allowed = loopback(client) and loopback(host) and (origin is None or window_origin(origin, headers.get("host", "")))
                if origin is None and headers.get("sec-fetch-site", "").strip().lower() == "cross-site":
                    allowed = False
                if not allowed and scope.get("method") in ("GET", "HEAD") and scope.get("path", "").startswith("/api/extensions/files/"):
                    allowed = loopback(client) and loopback(host)
                if (
                    not allowed
                    and scope["type"] == "http"
                    and scope.get("method") == "GET"
                    and scope.get("path") in ("/api/cloud/google/callback", "/api/connect/tiktok/callback/")
                    and headers.get("sec-fetch-mode", "navigate").strip().lower() == "navigate"
                    and headers.get("sec-fetch-dest", "document").strip().lower() == "document"
                ):
                    allowed = loopback(client) and loopback(host)
                if not allowed and remote_token():
                    # P11: remote access is off unless a token is set in the engine,
                    # and then every request must present it. Loopback is untouched.
                    allowed = headers.get("x-formcut-token") == remote_token()
        except ValueError:
            allowed = False
        if (
            scope["type"] == "http"
            and scope.get("method") in ("POST", "PUT", "PATCH", "DELETE")
            and scope.get("path", "").startswith("/api/")
        ):
            allowed = allowed and headers.get("x-formcut-local") == "1"
        keyless = False
        if allowed and not window_key.valid(headers.get(window_key.HEADER)) and not _without_key(scope, headers, through_network):
            allowed, keyless = False, True
        if not allowed:
            if scope["type"] == "websocket":
                return await send({"type": "websocket.close", "code": 1008})
            if through_network and scope.get("method") == "GET" and not scope.get("path", "").startswith("/api/"):
                return await RedirectResponse("/pair", status_code=303)(scope, receive, send)
            reason = window_key.REFUSED if keyless else "Local API request refused"
            return await PlainTextResponse(reason, status_code=403)(scope, receive, send)

        async def safe_send(message):
            if message["type"] == "http.response.start":
                message.setdefault("headers", []).append((b"x-content-type-options", b"nosniff"))
            await send(message)

        await self.app(scope, receive, safe_send)
