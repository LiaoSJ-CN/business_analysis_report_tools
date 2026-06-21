"""X-Forwarded-For trusted-proxy IP resolution (P3.5 / PY-12).

When the app sits behind a reverse proxy (nginx, HAProxy, etc.),
``request.client.host`` is the proxy's IP, not the real client.
This ASGI middleware rewrites the client address from
``X-Forwarded-For`` when the immediate peer is listed in
``settings.trusted_proxies``, so that downstream code—most
importantly the rate limiter—sees the real client IP.
"""

from __future__ import annotations

from ipaddress import ip_address, ip_network
from typing import Any

from starlette.types import ASGIApp, Receive, Scope, Send

from app.config import settings


def _parse_trusted(entries: list[str]) -> list[Any]:
    """Normalize trusted_proxies entries into ip_network objects."""
    nets: list[Any] = []
    for e in entries:
        try:
            nets.append(ip_network(e, strict=False))
        except ValueError:
            continue
    return nets


def _rightmost_untrusted(header_value: str, trusted_nets: list[Any]) -> str | None:
    """Walk *header_value* right-to-left; return the first hop NOT in *trusted_nets*.

    None if every hop (including the origin) is listed as trusted—an
    improbable config that would mask the real IP entirely.
    """
    hops = [h.strip() for h in header_value.split(",")]
    for hop in reversed(hops):
        if not hop:
            continue
        try:
            addr = ip_address(hop)
        except ValueError:
            continue
        if not any(addr in net for net in trusted_nets):
            return hop
    return None


class ProxyHeadersMiddleware:
    """Rewrite ``scope["client"]`` from X-Forwarded-For when the peer is trusted."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        trusted_nets = _parse_trusted(settings.trusted_proxies)
        if not trusted_nets:
            await self.app(scope, receive, send)
            return

        client = scope.get("client")
        if client is None:
            await self.app(scope, receive, send)
            return

        proxy_host = client[0]
        peer_is_trusted = False
        try:
            proxy_addr = ip_address(proxy_host)
            peer_is_trusted = any(proxy_addr in net for net in trusted_nets)
        except ValueError:
            pass

        if not peer_is_trusted:
            await self.app(scope, receive, send)
            return

        for header_name, header_value in scope.get("headers", []):
            if header_name.decode("latin-1").lower() == "x-forwarded-for":
                real_ip = _rightmost_untrusted(header_value.decode("latin-1"), trusted_nets)
                if real_ip:
                    scope["client"] = (real_ip, client[1])
                break

        await self.app(scope, receive, send)
