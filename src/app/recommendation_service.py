"""
Podcast recommendation service.

Uses a three-step pipeline:
  1. Tavily web search for podcast recommendations relevant to the user's shows.
  2. One LLM call to pick the best podcast from the search results.
  3. iTunes/Podcast Index lookup to find the RSS URL and artwork for that podcast.

Requires a configured Tavily API key; returns None when the key is absent.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

import litellm
import requests

from shared.config import Config

logger = logging.getLogger("global_logger")

_SEARCH_URL = "http://api.podcastindex.org/search"
_SEARCH_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/58.0.3029.110 Safari/537.36"
    )
}


def _get_tavily_api_key() -> Optional[str]:
    """Read Tavily key from env var first, then DB."""
    key = os.environ.get("TAVILY_API_KEY")
    if key:
        return key
    try:
        from app.models import AppSettings  # pylint: disable=import-outside-toplevel

        row = AppSettings.query.get(1)
        return getattr(row, "tavily_api_key", None) if row else None
    except Exception:  # pylint: disable=broad-except
        return None


def _call_llm(config: Config, messages: List[Dict[str, str]]) -> str:
    kwargs: Dict[str, Any] = {
        "model": config.llm_model,
        "messages": messages,
        "max_tokens": 256,
        "timeout": min(config.openai_timeout, 60),
    }
    if config.llm_api_key:
        kwargs["api_key"] = config.llm_api_key
    if config.openai_base_url:
        kwargs["api_base"] = config.openai_base_url

    response = litellm.completion(**kwargs)
    choices = getattr(response, "choices", None)
    if not choices:
        raise RuntimeError("LLM returned no choices")
    content = choices[0].message.content or ""
    return content.strip()


def _tavily_search(api_key: str, query: str) -> str:
    """Run a basic Tavily search and return concatenated snippets."""
    from tavily import TavilyClient  # pylint: disable=import-outside-toplevel

    client = TavilyClient(api_key=api_key)
    results = client.search(query=query, search_depth="basic", max_results=5)
    snippets = []
    for r in results.get("results", []):
        title = r.get("title", "")
        content = r.get("content", "")
        if content:
            snippets.append(f"[{title}] {content}")
    return "\n\n".join(snippets)


def _itunes_lookup(podcast_name: str) -> Optional[Dict[str, Any]]:
    """Search iTunes/Podcast Index for an RSS feed URL by name."""
    try:
        resp = requests.get(
            _SEARCH_URL,
            headers=_SEARCH_HEADERS,
            params={"term": podcast_name},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning("iTunes lookup failed for %r: %s", podcast_name, exc)
        return None

    for item in data.get("results") or []:
        feed_url = item.get("feedUrl")
        if not feed_url:
            continue
        return {
            "title": item.get("collectionName")
            or item.get("trackName")
            or podcast_name,
            "author": item.get("artistName") or "",
            "description": item.get("collectionCensoredName") or "",
            "rss_url": feed_url,
            "artwork_url": item.get("artworkUrl100") or item.get("artworkUrl600") or "",
        }
    return None


def get_recommendation(
    config: Config,
    current_feed_titles: List[str],
    dismissed_titles: List[str],
) -> Optional[Dict[str, Any]]:
    """
    Return a recommendation dict with keys: title, author, description,
    rss_url, artwork_url, reason. Returns None if Tavily is not configured
    or no suitable recommendation can be found.
    """
    tavily_api_key = _get_tavily_api_key()
    if not tavily_api_key or not current_feed_titles:
        return None

    # Build a search query from the user's podcast titles (no LLM call needed)
    sample_titles = current_feed_titles[:3]
    titles_str = ", ".join(f'"{t}"' for t in sample_titles)
    query = f"best podcast recommendations for listeners of {titles_str}"

    # Step 1: Tavily search
    try:
        snippets = _tavily_search(tavily_api_key, query)
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning("Tavily search failed: %s", exc)
        return None

    if not snippets:
        return None

    # Step 2: ONE LLM call — pick the best podcast from search results
    already_has = "\n".join(f"- {t}" for t in current_feed_titles)
    dismissed = (
        "\n".join(f"- {t}" for t in dismissed_titles) if dismissed_titles else "None"
    )

    prompt = (
        f"The user already listens to:\n{already_has}\n\n"
        f"Previously dismissed recommendations:\n{dismissed}\n\n"
        f"Web search results about podcast recommendations:\n{snippets}\n\n"
        "Recommend ONE specific podcast NOT in the user's list and NOT dismissed.\n"
        'Reply ONLY as JSON: {"podcast_name": "exact name", '
        '"reason": "one sentence why they will enjoy it"}'
    )

    try:
        raw = _call_llm(config, [{"role": "user", "content": prompt}])
        start = raw.find("{")
        end = raw.rfind("}") + 1
        choice: Dict[str, Any] = json.loads(raw[start:end]) if start >= 0 else {}
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning("LLM recommendation call failed: %s", exc)
        return None

    podcast_name = (choice.get("podcast_name") or "").strip()
    reason = (choice.get("reason") or "").strip()
    if not podcast_name:
        return None

    # Step 3: iTunes/Podcast Index lookup to get the RSS URL and artwork
    match = _itunes_lookup(podcast_name)
    if not match:
        return None

    match["reason"] = reason
    return match
