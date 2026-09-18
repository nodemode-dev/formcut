import ipaddress
from urllib.parse import urlsplit

from starlette.responses import PlainTextResponse


def loopback(value: str) -> bool:
    if value in ("localhost", "testclient", "testserver"):
        return True
    try:
        return ipaddress.ip_address(value).is_loopback
    except ValueError:
        return False


class LocalOnly:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket"):
            return await self.app(scope, receive, send)
        headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
        client = (scope.get("client") or ("",))[0]
        try:
            host = urlsplit("http://" + headers.get("host", "")).hostname or ""
            origin = headers.get("origin")
            origin_host = urlsplit(origin).hostname if origin else None
            allowed = loopback(client) and loopback(host) and (origin_host is None or loopback(origin_host))
        except ValueError:
            allowed = False
        if scope["type"] == "http" and scope.get("method") in ("POST", "PUT", "PATCH", "DELETE") and scope.get("path", "").startswith("/api/"):
            allowed = allowed and headers.get("x-formcut-local") == "1"
        if not allowed:
            if scope["type"] == "websocket":
                return await send({"type": "websocket.close", "code": 1008})
            return await PlainTextResponse("Local API request refused", status_code=403)(scope, receive, send)
        async def safe_send(message):
            if message["type"] == "http.response.start":
                message.setdefault("headers", []).append((b"x-content-type-options", b"nosniff"))
            await send(message)
        await self.app(scope, receive, safe_send)
