"""
Podcast recommendation service.

Pipeline (2 LLM calls, 1 Tavily search, 1 iTunes lookup):
  1. LLM derives the user's thematic taste and a focused search query from
     their podcast list — so Tavily never sees raw show names.
  2. Tavily fetches current web results for that query.
  3. LLM picks the best podcast from the results using the taste description.
  4. iTunes/Podcast Index resolves the RSS URL and artwork.

Requires a Tavily API key; returns None silently when absent.
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

_ITUNES_URL = "http://api.podcastindex.org/search"
_ITUNES_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/58.0.3029.110 Safari/537.36"
    )
}


def _get_tavily_api_key() -> Optional[str]:
    key = os.environ.get("TAVILY_API_KEY")
    if key:
        return key
    try:
        from app.models import AppSettings  # pylint: disable=import-outside-toplevel

        row = AppSettings.query.get(1)
        return getattr(row, "tavily_api_key", None) if row else None
    except Exception:  # pylint: disable=broad-except
        return None


def _call_llm(config: Config, prompt: str) -> str:
    kwargs: Dict[str, Any] = {
        "model": config.llm_model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 160,
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
    return (choices[0].message.content or "").strip()


def _parse_json(raw: str) -> Dict[str, Any]:
    start, end = raw.find("{"), raw.rfind("}") + 1
    if start < 0:
        return {}
    return json.loads(raw[start:end])


def _tavily_search(api_key: str, query: str) -> str:
    from tavily import TavilyClient  # pylint: disable=import-outside-toplevel

    client = TavilyClient(api_key=api_key)
    results = client.search(query=query, search_depth="basic", max_results=5)
    snippets = [
        f"[{r.get('title', '')}] {r.get('content', '')}"
        for r in results.get("results", [])
        if r.get("content")
    ]
    return "\n\n".join(snippets)


def _itunes_lookup(podcast_name: str) -> Optional[Dict[str, Any]]:
    try:
        resp = requests.get(
            _ITUNES_URL,
            headers=_ITUNES_HEADERS,
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
    rss_url, artwork_url, reason. Returns None when Tavily is not configured
    or no suitable recommendation can be found.
    """
    tavily_api_key = _get_tavily_api_key()
    if not tavily_api_key or not current_feed_titles:
        return None

    # ── Step 1: derive taste profile + search query (LLM call 1) ───────────
    # Dismissed titles are passed here so the model can pick an angle that
    # hasn't already been explored and avoid retreading the same ground.
    titles_block = "\n".join(f"- {t}" for t in current_feed_titles)
    dismissed_block = (
        "\n".join(f"- {t}" for t in dismissed_titles) if dismissed_titles else "None"
    )
    profile_prompt = (
        "You are a podcast recommendation analyst.\n\n"
        f"The listener subscribes to:\n{titles_block}\n\n"
        f"They have already dismissed these recommendations:\n{dismissed_block}\n\n"
        "Generate a targeted web search query to find them a NEW podcast they haven't tried.\n\n"
        "Rules for the search query (5-10 words):\n"
        "- Focus on specific themes, tone, genre, or style.\n"
        "- You MAY include one well-known show name as a reference point when it "
        "meaningfully sharpens the query (e.g. 'comedy fact podcasts similar to "
        "No Such Thing as a Fish'). Only do this when it genuinely helps.\n"
        "- Vary your approach — do not always use the same pattern. Sometimes "
        "lead with genre, sometimes mood, sometimes topic.\n"
        "- Use the dismissed list to explore a different angle from what was "
        "already tried.\n\n"
        "Also write a concise taste description (10-20 words) covering the key "
        "themes and tone — used internally, not for search.\n\n"
        'Reply ONLY as JSON: {"taste": "...", "search_query": "..."}\n'
        "Examples of good search queries:\n"
        '  "comedy fact podcasts similar to No Such Thing as a Fish"\n'
        '  "narrative investigative journalism true crime"\n'
        '  "bite-sized daily news briefing podcasts"\n'
        '  "long-form philosophy and ethics conversations"'
    )

    try:
        profile = _parse_json(_call_llm(config, profile_prompt))
        taste: str = (profile.get("taste") or "").strip()
        search_query: str = (profile.get("search_query") or "").strip()
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning("Taste profiling call failed: %s", exc)
        return None

    if not taste or not search_query:
        return None

    logger.info("Recommendation search query: %r | taste: %r", search_query, taste)

    # ── Step 2: Tavily search ────────────────────────────────────────────────
    try:
        snippets = _tavily_search(tavily_api_key, search_query)
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning("Tavily search failed: %s", exc)
        return None

    if not snippets:
        return None

    # ── Step 3: pick from results (LLM call 2) ──────────────────────────────
    already_has_block = "\n".join(f"- {t}" for t in current_feed_titles)

    pick_prompt = (
        f"Listener taste: {taste}\n\n"
        f"Already subscribed to:\n{already_has_block}\n\n"
        f"Previously dismissed (do not suggest these):\n{dismissed_block}\n\n"
        f"Podcast search results:\n{snippets}\n\n"
        "Pick ONE podcast from the results that best fits the listener's taste, "
        "is not already subscribed, and has not been dismissed.\n"
        'Reply ONLY as JSON: {"podcast_name": "exact name as it appears in the results", '
        '"reason": "one sentence personalised to their taste"}'
    )

    try:
        pick = _parse_json(_call_llm(config, pick_prompt))
        podcast_name: str = (pick.get("podcast_name") or "").strip()
        reason: str = (pick.get("reason") or "").strip()
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning("Pick call failed: %s", exc)
        return None

    if not podcast_name:
        return None

    # ── Step 4: resolve RSS URL via iTunes ───────────────────────────────────
    match = _itunes_lookup(podcast_name)
    if not match:
        return None

    match["reason"] = reason
    return match
