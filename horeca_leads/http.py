"""Tiny HTTP layer. In demo mode it serves fixture files instead of hitting the network."""
from __future__ import annotations

import logging
from pathlib import Path

import requests

log = logging.getLogger(__name__)


class Fetcher:
    def __init__(self, user_agent: str, timeout: int = 20, fixtures: dict[str, Path] | None = None):
        self.session = requests.Session()
        self.session.headers["User-Agent"] = user_agent
        self.timeout = timeout
        self.fixtures = fixtures  # url-prefix -> file; when set, the network is never used

    def get(self, url: str, params: dict | None = None) -> str | None:
        if self.fixtures is not None:
            for prefix, path in self.fixtures.items():
                if url.startswith(prefix):
                    return path.read_text(encoding="utf-8")
            return None
        try:
            r = self.session.get(url, params=params, timeout=self.timeout)
            r.raise_for_status()
            r.encoding = r.encoding or "utf-8"
            return r.text
        except requests.RequestException as e:
            log.warning("GET %s failed: %s", url, e)
            return None

    def post(self, url: str, data: dict) -> str | None:
        if self.fixtures is not None:
            for prefix, path in self.fixtures.items():
                if url.startswith(prefix):
                    return path.read_text(encoding="utf-8")
            return None
        try:
            r = self.session.post(url, data=data, timeout=max(self.timeout, 200))
            r.raise_for_status()
            return r.text
        except requests.RequestException as e:
            log.warning("POST %s failed: %s", url, e)
            return None
