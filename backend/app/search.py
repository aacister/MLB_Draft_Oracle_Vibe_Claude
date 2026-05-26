"""DuckDuckGo web search wrapper with file-based 24 h cache.

The Researcher agent uses this through the ``web_search`` function-tool to find
player news. Cached at ``./memory/search_cache/<sha256(query)>.json``.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

from ddgs import DDGS

from app.paths import SEARCH_CACHE_DIR

CACHE_TTL_SECONDS = 24 * 3600


def _cache_path(query: str) -> Path:
    digest = hashlib.sha256(query.encode("utf-8")).hexdigest()
    return SEARCH_CACHE_DIR / f"{digest}.json"


def web_search(query: str, *, max_results: int = 5, region: str = "us-en") -> list[dict[str, Any]]:
    """Return up to ``max_results`` DuckDuckGo results for the query.

    Results are cached for ``CACHE_TTL_SECONDS``. On cache hit, the live API is
    not contacted.
    """
    path = _cache_path(query)
    if path.exists() and (time.time() - path.stat().st_mtime) < CACHE_TTL_SECONDS:
        return json.loads(path.read_text())

    results = list(DDGS().text(query, max_results=max_results, region=region))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(results))
    return results
