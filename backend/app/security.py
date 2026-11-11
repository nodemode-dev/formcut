import ipaddress
import os
from urllib.parse import urlsplit

from starlette.responses import PlainTextResponse, RedirectResponse

from . import remote


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
        if not allowed:
            if scope["type"] == "websocket":
                return await send({"type": "websocket.close", "code": 1008})
            if through_network and scope.get("method") == "GET" and not scope.get("path", "").startswith("/api/"):
                return await RedirectResponse("/pair", status_code=303)(scope, receive, send)
            return await PlainTextResponse("Local API request refused", status_code=403)(scope, receive, send)

        async def safe_send(message):
            if message["type"] == "http.response.start":
                message.setdefault("headers", []).append((b"x-content-type-options", b"nosniff"))
            await send(message)

        await self.app(scope, receive, safe_send)
