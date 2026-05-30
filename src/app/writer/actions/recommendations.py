from datetime import datetime
from typing import Any, Dict

from app.extensions import db
from app.models import DismissedRecommendation, PendingRecommendation


def dismiss_recommendation_action(params: Dict[str, Any]) -> Dict[str, Any]:
    user_id = params.get("user_id")
    podcast_title = params["podcast_title"]
    podcast_rss_url = params.get("podcast_rss_url")

    PendingRecommendation.query.filter_by(user_id=user_id).delete()

    record = DismissedRecommendation(
        user_id=user_id,
        podcast_title=podcast_title,
        podcast_rss_url=podcast_rss_url,
        dismissed_at=datetime.utcnow(),
    )
    db.session.add(record)
    return {"dismissed": True, "podcast_title": podcast_title}


def save_pending_recommendation_action(params: Dict[str, Any]) -> Dict[str, Any]:
    user_id = params.get("user_id")

    PendingRecommendation.query.filter_by(user_id=user_id).delete()

    record = PendingRecommendation(
        user_id=user_id,
        title=params["title"],
        author=params.get("author") or "",
        description=params.get("description") or "",
        rss_url=params["rss_url"],
        artwork_url=params.get("artwork_url") or "",
        reason=params.get("reason") or "",
        created_at=datetime.utcnow(),
    )
    db.session.add(record)
    return {"saved": True, "title": params["title"]}


def clear_pending_recommendation_action(params: Dict[str, Any]) -> Dict[str, Any]:
    user_id = params.get("user_id")
    PendingRecommendation.query.filter_by(user_id=user_id).delete()
    return {"cleared": True}
