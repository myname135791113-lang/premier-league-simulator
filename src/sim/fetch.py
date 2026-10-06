"""Polite HTTP fetching with an on-disk cache.

Every download is written under data/raw/ exactly as received, so the
processed database can always be rebuilt without touching the network.
"""
import logging
import random
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

from . import config

log = logging.getLogger(__name__)

USER_AGENT = "FootballMatchSimulator/0.1 (personal research project)"
RETRY_STATUS = {429, 500, 502, 503, 504}


class FetchError(RuntimeError):
    pass


class Fetcher:
    def __init__(self, min_delay: float | None = None):
        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self.min_delay = config.load()["fetch"]["min_delay_seconds"] if min_delay is None else min_delay
        self._last_hit: dict[str, float] = {}

    def get(self, url: str, cache: Path, *, refresh: bool = False,
            headers: dict | None = None, retries: int = 4) -> bytes:
        """Return the body of `url`, from `cache` when present unless `refresh`."""
        if cache.exists() and not refresh:
            return cache.read_bytes()

        host = urlparse(url).netloc
        for attempt in range(retries):
            self._wait(host)
            try:
                resp = self.session.get(url, headers=headers, timeout=30)
            except (requests.ConnectionError, requests.Timeout) as exc:
                log.warning("%s: %s (attempt %d)", url, exc.__class__.__name__, attempt + 1)
                time.sleep(5 * 2 ** attempt)
                continue
            finally:
                self._last_hit[host] = time.monotonic()

            if resp.status_code == 200:
                cache.parent.mkdir(parents=True, exist_ok=True)
                tmp = cache.with_suffix(cache.suffix + ".part")
                tmp.write_bytes(resp.content)
                tmp.replace(cache)
                return resp.content
            if resp.status_code in RETRY_STATUS:
                log.warning("%s: HTTP %d (attempt %d)", url, resp.status_code, attempt + 1)
                time.sleep(5 * 2 ** attempt)
                continue
            raise FetchError(f"{url}: HTTP {resp.status_code}")
        raise FetchError(f"{url}: gave up after {retries} attempts")

    def _wait(self, host: str) -> None:
        elapsed = time.monotonic() - self._last_hit.get(host, 0.0)
        if elapsed < self.min_delay:
            time.sleep(self.min_delay - elapsed + random.uniform(0, 0.4))
