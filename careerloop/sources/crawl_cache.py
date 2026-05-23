"""Shared crawl cache — reuse Playwright results across users for the same role+city."""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path


class CrawlCache:
    TTL_SECONDS = 8 * 3600  # 8 hours

    def __init__(self, root: str) -> None:
        self._cache_dir = Path(root) / "cache" / "crawl"
        try:
            self._cache_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, role: str, city: str) -> list[dict] | None:
        try:
            path = self._path(role, city)
            if not path.exists():
                return None
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("expires_at", 0) < time.time():
                return None
            return data.get("jobs")
        except Exception:
            return None

    def set(self, role: str, city: str, jobs: list[dict]) -> None:
        try:
            now = time.time()
            payload = {
                "role": role.strip().lower(),
                "city": city.strip().lower(),
                "cached_at": now,
                "expires_at": now + self.TTL_SECONDS,
                "job_count": len(jobs),
                "jobs": jobs,
            }
            path = self._path(role, city)
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.rename(path)
        except Exception:
            pass

    def clear(self, role: str, city: str) -> None:
        try:
            self._path(role, city).unlink(missing_ok=True)
        except Exception:
            pass

    def stats(self) -> dict:
        total_keys = 0
        total_jobs = 0
        oldest_entry: float | None = None
        try:
            for f in self._cache_dir.glob("*.json"):
                try:
                    data = json.loads(f.read_text(encoding="utf-8"))
                    total_keys += 1
                    total_jobs += data.get("job_count", 0)
                    cached_at = data.get("cached_at")
                    if cached_at is not None:
                        if oldest_entry is None or cached_at < oldest_entry:
                            oldest_entry = cached_at
                except Exception:
                    pass
        except Exception:
            pass
        return {
            "total_keys": total_keys,
            "total_jobs": total_jobs,
            "oldest_entry": oldest_entry,
        }

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _key(self, role: str, city: str) -> str:
        normalized = self._normalize(role) + "|" + self._normalize(city)
        return hashlib.sha256(normalized.encode()).hexdigest()

    def _path(self, role: str, city: str) -> Path:
        return self._cache_dir / f"{self._key(role, city)}.json"

    @staticmethod
    def _normalize(value: str) -> str:
        return value.strip().lower().replace(" ", "_")
