"""Tests for BoundaryRefiner._get_context, _heuristic_refine, _validate, and mocked refine."""

import json
import logging
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest

from podcast_processor.boundary_refiner import (
    MAX_END_EXTENSION_SECONDS,
    MAX_START_EXTENSION_SECONDS,
    BoundaryRefinement,
    BoundaryRefiner,
)
from shared.test_utils import create_standard_test_config


def _segs(*start_times: float) -> List[Dict[str, Any]]:
    return [
        {"start_time": t, "end_time": t + 1.0, "text": f"seg at {t}"}
        for t in start_times
    ]


@pytest.fixture
def refiner() -> BoundaryRefiner:
    return BoundaryRefiner(
        config=create_standard_test_config(),
        logger=logging.getLogger("test_boundary_refiner"),
    )


# ---------------------------------------------------------------------------
# _get_context
# ---------------------------------------------------------------------------


class TestGetContext:
    def test_empty_segments_returns_empty(self, refiner: BoundaryRefiner) -> None:
        assert refiner._get_context(10.0, 20.0, []) == []

    def test_no_segments_in_range_returns_empty(self, refiner: BoundaryRefiner) -> None:
        segs = _segs(0.0, 5.0, 25.0, 30.0)
        assert refiner._get_context(10.0, 20.0, segs) == []

    def test_eight_context_segments_on_each_side(
        self, refiner: BoundaryRefiner
    ) -> None:
        segs = _segs(*range(20))
        # ad covers t=10 (index 10); window = [max(0,10-8), min(20,10+9)] = [2, 19]
        ctx = refiner._get_context(10.0, 10.0, segs)
        assert ctx[0]["start_time"] == 2.0
        assert ctx[-1]["start_time"] == 18.0

    def test_clamped_at_list_start(self, refiner: BoundaryRefiner) -> None:
        segs = _segs(*range(10))
        # ad at t=1 (index 1); start_idx = max(0, 1-8) = 0
        ctx = refiner._get_context(1.0, 1.0, segs)
        assert ctx[0]["start_time"] == 0.0

    def test_clamped_at_list_end(self, refiner: BoundaryRefiner) -> None:
        segs = _segs(*range(10))
        # ad at t=9 (index 9); end_idx = min(10, 9+9) = 10
        ctx = refiner._get_context(9.0, 9.0, segs)
        assert ctx[-1]["start_time"] == 9.0

    def test_multiple_ad_segments_covered(self, refiner: BoundaryRefiner) -> None:
        segs = _segs(*range(20))
        # ad covers t=8..12; start_idx=0, end_idx=20 → full list
        ctx = refiner._get_context(8.0, 12.0, segs)
        assert ctx[0]["start_time"] == 0.0
        assert ctx[-1]["start_time"] == 19.0


# ---------------------------------------------------------------------------
# _heuristic_refine
# ---------------------------------------------------------------------------


class TestHeuristicRefine:
    def test_no_pattern_keeps_original_boundaries(
        self, refiner: BoundaryRefiner
    ) -> None:
        segs = [
            {"start_time": 8.0, "end_time": 9.0, "text": "hello world"},
            {"start_time": 12.0, "end_time": 13.0, "text": "goodbye world"},
        ]
        result = refiner._heuristic_refine(10.0, 11.0, segs)
        assert result.refined_start == 10.0
        assert result.refined_end == 11.0

    def test_intro_pattern_moves_start_earlier(self, refiner: BoundaryRefiner) -> None:
        segs = [
            {"start_time": 7.0, "end_time": 8.0, "text": "brought to you by"},
            {"start_time": 12.0, "end_time": 13.0, "text": "no match here"},
        ]
        result = refiner._heuristic_refine(10.0, 11.0, segs)
        assert result.refined_start == 7.0
        assert result.refined_end == 11.0

    def test_outro_pattern_moves_end_later(self, refiner: BoundaryRefiner) -> None:
        segs = [
            {
                "start_time": 12.0,
                "end_time": 14.0,
                "text": "visit example.com for more",
            },
        ]
        result = refiner._heuristic_refine(10.0, 11.0, segs)
        assert result.refined_end == 14.0
        assert result.refined_start == 10.0

    def test_outro_without_end_time_defaults_to_start_plus_five(
        self, refiner: BoundaryRefiner
    ) -> None:
        segs = [{"start_time": 15.0, "text": "use code SAVE"}]  # no end_time key
        result = refiner._heuristic_refine(10.0, 14.0, segs)
        assert result.refined_end == pytest.approx(20.0)

    def test_sponsor_pattern_matches(self, refiner: BoundaryRefiner) -> None:
        segs = [{"start_time": 8.0, "end_time": 9.0, "text": "our sponsor today"}]
        result = refiner._heuristic_refine(10.0, 11.0, segs)
        assert result.refined_start == 8.0

    def test_reason_strings_are_heuristic(self, refiner: BoundaryRefiner) -> None:
        result = refiner._heuristic_refine(10.0, 11.0, [])
        assert result.start_adjustment_reason == "heuristic"
        assert result.end_adjustment_reason == "heuristic"


# ---------------------------------------------------------------------------
# _validate
# ---------------------------------------------------------------------------


class TestValidate:
    def test_valid_refinement_passes_through(self, refiner: BoundaryRefiner) -> None:
        r = BoundaryRefinement(9.0, 21.0, "ok", "ok")
        result = refiner._validate(10.0, 20.0, r)
        assert result.refined_start == 9.0
        assert result.refined_end == 21.0

    def test_start_clamped_when_extended_too_far(
        self, refiner: BoundaryRefiner
    ) -> None:
        far_start = 10.0 - MAX_START_EXTENSION_SECONDS - 5.0
        r = BoundaryRefinement(far_start, 20.0, "x", "x")
        result = refiner._validate(10.0, 20.0, r)
        assert result.refined_start == pytest.approx(10.0 - MAX_START_EXTENSION_SECONDS)

    def test_end_clamped_when_extended_too_far(self, refiner: BoundaryRefiner) -> None:
        far_end = 20.0 + MAX_END_EXTENSION_SECONDS + 5.0
        r = BoundaryRefinement(10.0, far_end, "x", "x")
        result = refiner._validate(10.0, 20.0, r)
        assert result.refined_end == pytest.approx(20.0 + MAX_END_EXTENSION_SECONDS)

    def test_inverted_boundaries_reset_to_original(
        self, refiner: BoundaryRefiner
    ) -> None:
        r = BoundaryRefinement(15.0, 5.0, "x", "x")  # start > end
        result = refiner._validate(10.0, 20.0, r)
        assert result.refined_start == 10.0
        assert result.refined_end == 20.0

    def test_equal_boundaries_reset_to_original(self, refiner: BoundaryRefiner) -> None:
        r = BoundaryRefinement(12.0, 12.0, "x", "x")
        result = refiner._validate(10.0, 20.0, r)
        assert result.refined_start == 10.0
        assert result.refined_end == 20.0


# ---------------------------------------------------------------------------
# refine — mocked LLM
# ---------------------------------------------------------------------------


def _llm_response(refined_start: float, refined_end: float) -> MagicMock:
    payload = json.dumps(
        {
            "refined_start": refined_start,
            "refined_end": refined_end,
            "start_adjustment_reason": "llm",
            "end_adjustment_reason": "llm",
        }
    )
    choice = MagicMock()
    choice.message.content = payload
    resp = MagicMock()
    resp.choices = [choice]
    return resp


class TestRefine:
    @patch("podcast_processor.boundary_refiner.writer_client")
    @patch("podcast_processor.boundary_refiner.litellm.completion")
    def test_successful_llm_parse_returns_refined_boundaries(
        self,
        mock_completion: MagicMock,
        mock_writer: MagicMock,
        refiner: BoundaryRefiner,
    ) -> None:
        mock_completion.return_value = _llm_response(9.5, 20.5)
        result = refiner.refine(10.0, 20.0, 0.9, _segs(*range(20)))
        assert result.refined_start == pytest.approx(9.5)
        assert result.refined_end == pytest.approx(20.5)

    @patch("podcast_processor.boundary_refiner.writer_client")
    @patch("podcast_processor.boundary_refiner.litellm.completion")
    def test_unparseable_json_falls_back_to_heuristic(
        self,
        mock_completion: MagicMock,
        mock_writer: MagicMock,
        refiner: BoundaryRefiner,
    ) -> None:
        choice = MagicMock()
        choice.message.content = "I cannot determine the boundaries."
        resp = MagicMock()
        resp.choices = [choice]
        mock_completion.return_value = resp
        result = refiner.refine(10.0, 20.0, 0.9, _segs(*range(20)))
        # No heuristic patterns in generic segment text → original values
        assert result.refined_start == 10.0
        assert result.refined_end == 20.0

    @patch("podcast_processor.boundary_refiner.writer_client")
    @patch("podcast_processor.boundary_refiner.litellm.completion")
    def test_llm_exception_falls_back_to_heuristic(
        self,
        mock_completion: MagicMock,
        mock_writer: MagicMock,
        refiner: BoundaryRefiner,
    ) -> None:
        mock_completion.side_effect = RuntimeError("network error")
        result = refiner.refine(10.0, 20.0, 0.9, _segs(*range(20)))
        assert result.refined_start == 10.0
        assert result.refined_end == 20.0

    @patch("podcast_processor.boundary_refiner.writer_client")
    @patch("podcast_processor.boundary_refiner.litellm.completion")
    def test_validate_clamps_overshooting_llm_response(
        self,
        mock_completion: MagicMock,
        mock_writer: MagicMock,
        refiner: BoundaryRefiner,
    ) -> None:
        # LLM returns start well before allowed window
        mock_completion.return_value = _llm_response(
            10.0 - MAX_START_EXTENSION_SECONDS - 10.0, 20.0
        )
        result = refiner.refine(10.0, 20.0, 0.9, _segs(*range(20)))
        assert result.refined_start >= 10.0 - MAX_START_EXTENSION_SECONDS
