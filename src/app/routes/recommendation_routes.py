import logging

from flask import Blueprint, g, jsonify, request
from flask.typing import ResponseReturnValue

from app.auth import is_auth_enabled
from app.extensions import db
from app.models import DismissedRecommendation, Feed, UserFeed
from app.recommendation_service import get_recommendation
from app.runtime_config import config as runtime_config
from app.writer.client import writer_client

logger = logging.getLogger("global_logger")

recommendation_bp = Blueprint("recommendations", __name__)


def _current_user():
    return getattr(g, "current_user", None)


@recommendation_bp.route("/api/recommendations", methods=["GET"])
def get_recommendation_endpoint() -> ResponseReturnValue:
    user = _current_user()

    if is_auth_enabled() and user is None:
        return jsonify({"error": "Authentication required."}), 401

    if user is not None:
        feeds = (
            Feed.query.join(UserFeed, UserFeed.feed_id == Feed.id)
            .filter(UserFeed.user_id == user.id)
            .all()
        )
        dismissed = DismissedRecommendation.query.filter_by(user_id=user.id).all()
    else:
        feeds = Feed.query.all()
        dismissed = DismissedRecommendation.query.filter_by(user_id=None).all()

    feed_titles = [f.title for f in feeds if f.title]
    dismissed_titles = [d.podcast_title for d in dismissed]

    try:
        result = get_recommendation(runtime_config, feed_titles, dismissed_titles)
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("Recommendation service error: %s", exc)
        return jsonify({"error": "Failed to generate recommendation", "detail": str(exc)}), 500

    if result is None:
        return jsonify({"recommendation": None}), 200

    return jsonify({"recommendation": result}), 200


@recommendation_bp.route("/api/recommendations/dismiss", methods=["POST"])
def dismiss_recommendation_endpoint() -> ResponseReturnValue:
    user = _current_user()

    if is_auth_enabled() and user is None:
        return jsonify({"error": "Authentication required."}), 401

    payload = request.get_json(silent=True) or {}
    podcast_title = payload.get("podcast_title", "").strip()
    podcast_rss_url = payload.get("podcast_rss_url", "").strip() or None

    if not podcast_title:
        return jsonify({"error": "podcast_title is required"}), 400

    user_id = user.id if user else None

    result = writer_client.action(
        "dismiss_recommendation",
        {
            "user_id": user_id,
            "podcast_title": podcast_title,
            "podcast_rss_url": podcast_rss_url,
        },
        wait=True,
    )
    if not result or not result.success:
        return jsonify({"error": getattr(result, "error", "Failed to dismiss")}), 500

    return jsonify({"status": "dismissed", "podcast_title": podcast_title}), 200
