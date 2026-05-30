"""
Podcast recommendation service.

Uses a two-step LLM pipeline:
  1. Ask the LLM to generate search terms based on the user's podcasts.
  2. Query the podcast search API, then ask the LLM to pick the best match.

This gives the model effective access to a live podcast catalog without
requiring a separate web-search API key.
"""
from __future__ import annotations

import json
import logging
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


def _call_llm(config: Config, messages: List[Dict[str, str]]) -> str:
    kwargs: Dict[str, Any] = {
        "model": config.llm_model,
        "messages": messages,
        "max_tokens": 512,
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


def _search_podcasts(term: str) -> List[Dict[str, Any]]:
    try:
        resp = requests.get(
            _SEARCH_URL,
            headers=_SEARCH_HEADERS,
            params={"term": term},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning("Podcast search failed for %r: %s", term, exc)
        return []

    results = []
    for item in (data.get("results") or [])[:5]:
        feed_url = item.get("feedUrl")
        if not feed_url:
            continue
        results.append(
            {
                "title": item.get("collectionName") or item.get("trackName") or "",
                "author": item.get("artistName") or "",
                "description": item.get("collectionCensoredName") or "",
                "feedUrl": feed_url,
                "artworkUrl": item.get("artworkUrl100") or item.get("artworkUrl600") or "",
                "genres": item.get("genres") or [],
            }
        )
    return results


def get_recommendation(
    config: Config,
    current_feed_titles: List[str],
    dismissed_titles: List[str],
) -> Optional[Dict[str, Any]]:
    """
    Returns a dict with keys: title, author, description, rss_url, artwork_url, reason.
    Returns None if no suitable recommendation can be generated.
    """
    if not current_feed_titles:
        return None

    feeds_summary = "\n".join(f"- {t}" for t in current_feed_titles)
    dismissed_summary = (
        "\n".join(f"- {t}" for t in dismissed_titles) if dismissed_titles else "None"
    )

    # Step 1: ask the LLM for 2-3 search terms
    step1_prompt = (
        "You are a podcast recommendation assistant.\n"
        "The user currently listens to these podcasts:\n"
        f"{feeds_summary}\n\n"
        "Generate 2 short search queries (2-4 words each) to find NEW podcasts they would enjoy. "
        "These queries will be sent to a podcast search engine.\n"
        "Reply with ONLY a JSON array of strings, e.g. [\"true crime stories\", \"history mysteries\"]."
    )
    try:
        step1_raw = _call_llm(config, [{"role": "user", "content": step1_prompt}])
        # Extract JSON array from the response
        start = step1_raw.find("[")
        end = step1_raw.rfind("]") + 1
        search_terms: List[str] = json.loads(step1_raw[start:end]) if start >= 0 else []
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning("Step 1 LLM call failed: %s", exc)
        return None

    if not search_terms:
        return None

    # Step 2: search for podcasts using the generated terms
    candidates: List[Dict[str, Any]] = []
    seen_titles: set[str] = set(t.lower() for t in current_feed_titles + dismissed_titles)
    for term in search_terms[:2]:
        for result in _search_podcasts(term):
            if result["title"].lower() not in seen_titles:
                candidates.append(result)
                seen_titles.add(result["title"].lower())

    if not candidates:
        return None

    # Deduplicate and cap
    candidates = candidates[:12]

    candidates_text = "\n".join(
        f"{i+1}. \"{c['title']}\" by {c['author']} — {c['description'] or c['genres']}"
        for i, c in enumerate(candidates)
    )

    # Step 3: ask the LLM to pick the best one
    step2_prompt = (
        "You are a podcast recommendation assistant.\n"
        "The user currently listens to:\n"
        f"{feeds_summary}\n\n"
        "Previously dismissed recommendations (do not suggest these):\n"
        f"{dismissed_summary}\n\n"
        "From the following search results, pick the single BEST new podcast for this user "
        "that they don't already have and haven't dismissed:\n"
        f"{candidates_text}\n\n"
        "Reply with ONLY a JSON object with these keys:\n"
        '  "index": <1-based index of chosen podcast>,\n'
        '  "reason": <one sentence explaining why they would enjoy it>\n'
        "Example: {\"index\": 3, \"reason\": \"You enjoy history, and this dives deep into forgotten empires.\"}"
    )
    try:
        step2_raw = _call_llm(config, [{"role": "user", "content": step2_prompt}])
        start = step2_raw.find("{")
        end = step2_raw.rfind("}") + 1
        choice: Dict[str, Any] = json.loads(step2_raw[start:end]) if start >= 0 else {}
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning("Step 2 LLM call failed: %s", exc)
        return None

    idx = choice.get("index")
    reason = choice.get("reason", "")
    if not isinstance(idx, int) or idx < 1 or idx > len(candidates):
        return None

    picked = candidates[idx - 1]
    return {
        "title": picked["title"],
        "author": picked["author"],
        "description": picked["description"],
        "rss_url": picked["feedUrl"],
        "artwork_url": picked["artworkUrl"],
        "reason": reason,
    }
