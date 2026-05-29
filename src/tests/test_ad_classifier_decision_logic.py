"""
Tests for AdClassifier's pure decision logic: confidence demotion for
self-promo/educational content and the neighbour-expansion scoring used by
boundary refinement. These functions directly control whether (and how
confidently) a segment is recorded as an ad, so they deserve explicit tests.
"""

from typing import Any
from unittest.mock import patch

import pytest

from podcast_processor.ad_classifier import AdClassifier
from shared.test_utils import create_test_config


def _make_classifier(**config_overrides: Any) -> AdClassifier:
    with patch("podcast_processor.ad_classifier.db.session") as mock_session:
        return AdClassifier(
            config=create_test_config(**config_overrides), db_session=mock_session
        )


class TestAdjustConfidence:
    def test_no_content_type_is_unchanged(self) -> None:
        classifier = _make_classifier()
        assert (
            classifier._adjust_confidence(base_confidence=0.9, content_type=None) == 0.9
        )

    @pytest.mark.parametrize(
        "content_type", ["educational/self_promo", "technical_discussion"]
    )
    def test_educational_and_technical_demoted_by_quarter(
        self, content_type: str
    ) -> None:
        classifier = _make_classifier()
        result = classifier._adjust_confidence(
            base_confidence=0.9, content_type=content_type
        )
        assert result == pytest.approx(0.65)

    def test_transition_demoted_by_tenth(self) -> None:
        classifier = _make_classifier()
        result = classifier._adjust_confidence(
            base_confidence=0.9, content_type="transition"
        )
        assert result == pytest.approx(0.8)

    def test_demotion_clamped_at_zero(self) -> None:
        classifier = _make_classifier()
        result = classifier._adjust_confidence(
            base_confidence=0.1, content_type="technical_discussion"
        )
        assert result == 0.0

    def test_unrecognized_content_type_is_unchanged(self) -> None:
        classifier = _make_classifier()
        result = classifier._adjust_confidence(
            base_confidence=0.77, content_type="promotional_external"
        )
        assert result == 0.77


class TestShouldExpandNeighbor:
    def test_without_refinement_only_strong_cue_expands(self) -> None:
        classifier = _make_classifier(enable_boundary_refinement=False)
        assert classifier._should_expand_neighbor(
            has_strong_cue=True, is_transition=False, gap_seconds=999.0
        )
        assert not classifier._should_expand_neighbor(
            has_strong_cue=False, is_transition=True, gap_seconds=1.0
        )

    def test_with_refinement_cue_or_transition_expands(self) -> None:
        classifier = _make_classifier(enable_boundary_refinement=True)
        assert classifier._should_expand_neighbor(
            has_strong_cue=True, is_transition=False, gap_seconds=999.0
        )
        assert classifier._should_expand_neighbor(
            has_strong_cue=False, is_transition=True, gap_seconds=999.0
        )

    def test_with_refinement_small_gap_expands_otherwise_not(self) -> None:
        classifier = _make_classifier(enable_boundary_refinement=True)
        assert classifier._should_expand_neighbor(
            has_strong_cue=False, is_transition=False, gap_seconds=10.0
        )
        assert not classifier._should_expand_neighbor(
            has_strong_cue=False, is_transition=False, gap_seconds=10.1
        )


class TestNeighborConfidence:
    def test_default_and_transition_baselines(self) -> None:
        assert AdClassifier._neighbor_confidence(
            has_strong_cue=False,
            is_transition=False,
            is_self_promo=False,
            gap_seconds=5.0,
        ) == pytest.approx(0.75)
        assert AdClassifier._neighbor_confidence(
            has_strong_cue=False,
            is_transition=True,
            is_self_promo=False,
            gap_seconds=5.0,
        ) == pytest.approx(0.72)

    def test_strong_cue_depends_on_gap(self) -> None:
        assert AdClassifier._neighbor_confidence(
            has_strong_cue=True,
            is_transition=False,
            is_self_promo=False,
            gap_seconds=10.0,
        ) == pytest.approx(0.85)
        assert AdClassifier._neighbor_confidence(
            has_strong_cue=True,
            is_transition=False,
            is_self_promo=False,
            gap_seconds=10.1,
        ) == pytest.approx(0.8)

    def test_self_promo_demotes_but_floors_at_half(self) -> None:
        # 0.72 baseline - 0.25 = 0.47 -> floored to 0.5
        assert AdClassifier._neighbor_confidence(
            has_strong_cue=False,
            is_transition=True,
            is_self_promo=True,
            gap_seconds=5.0,
        ) == pytest.approx(0.5)
        # 0.85 strong cue - 0.25 = 0.60
        assert AdClassifier._neighbor_confidence(
            has_strong_cue=True,
            is_transition=False,
            is_self_promo=True,
            gap_seconds=5.0,
        ) == pytest.approx(0.6)
