"""Minimalny klient HTTP z cache na dysku (bez zaleznosci zewnetrznych)."""

from __future__ import annotations

import gzip
import hashlib
import io
import time
import urllib.error
import urllib.request
from pathlib import Path

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0 Safari/537.36 basket-lab/1.0"
)


class HttpError(RuntimeError):
    def __init__(self, url: str, status: int):
        super().__init__(f"HTTP {status} dla {url}")
        self.url = url
        self.status = status


class Fetcher:
    """Pobiera zasoby i trzyma kopie w katalogu cache."""

    def __init__(self, cache_dir: Path | str, ttl: float | None = None, delay: float = 0.3):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl = ttl
        self.delay = delay
        self._last_call = 0.0

    def _cache_path(self, url: str, suffix: str) -> Path:
        key = hashlib.sha1(url.encode("utf-8")).hexdigest()[:20]
        return self.cache_dir / f"{key}{suffix}"

    def get(self, url: str, *, suffix: str = ".bin", force: bool = False) -> bytes:
        path = self._cache_path(url, suffix)
        if not force and path.exists():
            if self.ttl is None or (time.time() - path.stat().st_mtime) < self.ttl:
                return path.read_bytes()

        wait = self.delay - (time.time() - self._last_call)
        if wait > 0:
            time.sleep(wait)
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "*/*",
                "Accept-Encoding": "gzip",
                "Accept-Language": "pl,en;q=0.8",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read()
                if resp.headers.get("Content-Encoding") == "gzip":
                    raw = gzip.GzipFile(fileobj=io.BytesIO(raw)).read()
        except urllib.error.HTTPError as exc:  # pragma: no cover - siec
            raise HttpError(url, exc.code) from exc
        finally:
            self._last_call = time.time()

        path.write_bytes(raw)
        return raw

    def get_text(self, url: str, *, encoding: str = "utf-8", **kw) -> str:
        return self.get(url, **kw).decode(encoding, errors="replace")

    def get_json(self, url: str, **kw):
        import json

        return json.loads(self.get(url, suffix=".json", **kw).decode("utf-8"))
