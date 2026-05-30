from datetime import datetime
from typing import Any, Dict

from app.extensions import db
from app.models import DismissedRecommendation


def dismiss_recommendation_action(params: Dict[str, Any]) -> Dict[str, Any]:
    user_id = params.get("user_id")
    podcast_title = params["podcast_title"]
    podcast_rss_url = params.get("podcast_rss_url")

    record = DismissedRecommendation(
        user_id=user_id,
        podcast_title=podcast_title,
        podcast_rss_url=podcast_rss_url,
        dismissed_at=datetime.utcnow(),
    )
    db.session.add(record)
    return {"dismissed": True, "podcast_title": podcast_title}
