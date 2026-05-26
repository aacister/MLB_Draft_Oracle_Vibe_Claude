"""Tests for the DuckDuckGo search wrapper."""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app import search as search_module
from app.search import CACHE_TTL_SECONDS, _cache_path, web_search


@pytest.fixture
def isolated_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(search_module, "SEARCH_CACHE_DIR", tmp_path)
    return tmp_path


class TestCachePath:
    def test_deterministic_for_same_query(self, isolated_cache: Path) -> None:
        assert _cache_path("Aaron Judge stats") == _cache_path("Aaron Judge stats")

    def test_different_for_different_queries(self, isolated_cache: Path) -> None:
        assert _cache_path("a") != _cache_path("b")


class TestWebSearch:
    def test_calls_ddgs_on_miss_and_writes_cache(self, isolated_cache: Path) -> None:
        results = [{"title": "T", "href": "https://x", "body": "B"}]
        mock_ddgs = MagicMock()
        mock_ddgs.text.return_value = iter(results)
        with patch("app.search.DDGS", return_value=mock_ddgs):
            out = web_search("Aaron Judge stats")

        assert out == results
        mock_ddgs.text.assert_called_once_with(
            "Aaron Judge stats", max_results=5, region="us-en"
        )
        assert _cache_path("Aaron Judge stats").exists()

    def test_uses_cache_within_ttl(self, isolated_cache: Path) -> None:
        cached = [{"title": "Cached"}]
        _cache_path("query").write_text(json.dumps(cached))

        with patch("app.search.DDGS") as mock_ctor:
            out = web_search("query")

        mock_ctor.assert_not_called()
        assert out == cached

    def test_expired_cache_re_fetches(self, isolated_cache: Path) -> None:
        path = _cache_path("query")
        path.write_text(json.dumps([{"old": True}]))
        # Force mtime to be ancient
        ancient = time.time() - (CACHE_TTL_SECONDS + 1000)
        import os
        os.utime(path, (ancient, ancient))

        fresh = [{"title": "Fresh"}]
        mock_ddgs = MagicMock()
        mock_ddgs.text.return_value = iter(fresh)
        with patch("app.search.DDGS", return_value=mock_ddgs):
            out = web_search("query")

        assert out == fresh
        mock_ddgs.text.assert_called_once()

    def test_max_results_param_passed_through(self, isolated_cache: Path) -> None:
        mock_ddgs = MagicMock()
        mock_ddgs.text.return_value = iter([])
        with patch("app.search.DDGS", return_value=mock_ddgs):
            web_search("q", max_results=3)
        mock_ddgs.text.assert_called_once_with("q", max_results=3, region="us-en")
