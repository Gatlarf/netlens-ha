"""Small client for the Netlens HTTP API (read-only)."""

from __future__ import annotations

import asyncio
from typing import Any
from urllib.parse import urlparse

import aiohttp

from .const import SUPPORTED_API


class NetlensError(Exception):
    """Base class for Netlens API problems."""


class NetlensConnectionError(NetlensError):
    """Netlens could not be reached."""


class NetlensAuthError(NetlensError):
    """The token was refused."""


class NetlensApiVersionError(NetlensError):
    """Netlens answers with a summary format this integration does not know."""


def normalize_url(url: str) -> str:
    """'192.168.0.189:8080' -> 'http://192.168.0.189:8080' (Netlens listens on plain HTTP unless you put a proxy in front)."""
    url = url.strip()
    if "://" not in url:
        url = "http://" + url
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError("invalid URL")
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path.rstrip('/')}"


class NetlensApi:
    """Talks to one Netlens instance."""

    def __init__(self, session: aiohttp.ClientSession, url: str, token: str) -> None:
        self._session = session
        self.url = normalize_url(url)
        self._headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        try:
            async with asyncio.timeout(20):
                async with self._session.get(f"{self.url}{path}", headers=self._headers, params=params) as resp:
                    if resp.status == 401:
                        raise NetlensAuthError("the token was refused")
                    if resp.status == 404:
                        raise NetlensApiVersionError("this Netlens is too old: it has no /api/stats/summary (update Netlens)")
                    if resp.status >= 400:
                        raise NetlensConnectionError(f"Netlens answered HTTP {resp.status}")
                    try:
                        return await resp.json(content_type=None)
                    except (aiohttp.ContentTypeError, ValueError) as exc:
                        raise NetlensConnectionError("this does not look like a Netlens address (the answer is not JSON)") from exc
        except NetlensError:
            raise
        except TimeoutError as exc:
            raise NetlensConnectionError("Netlens did not answer in time") from exc
        except aiohttp.ClientError as exc:
            raise NetlensConnectionError(f"cannot connect to Netlens: {exc}") from exc

    async def summary(self) -> dict[str, Any]:
        """The headline numbers, scan state, plugin health and the device list."""
        data = await self._get("/api/stats/summary")
        if not isinstance(data, dict) or data.get("api") != SUPPORTED_API:
            raise NetlensApiVersionError(
                f"unsupported summary format (api {data.get('api') if isinstance(data, dict) else None}, expected {SUPPORTED_API}); update the integration or Netlens"
            )
        return data

    async def events(self, since_id: int) -> list[dict[str, Any]]:
        """Events Netlens logged after `since_id`, oldest first."""
        data = await self._get("/api/events", {"since_id": since_id, "limit": 500})
        return sorted(data, key=lambda e: e["id"]) if isinstance(data, list) else []
