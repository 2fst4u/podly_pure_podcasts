import pytest
from pydantic import ValidationError

from podcast_processor.model_output import (
    AdSegmentPrediction,
    AdSegmentPredictionList,
    _attempt_json_repair,
    clean_and_parse_model_output,
)


def test_clean_parse_output() -> None:
    model_outupt = """
extra stuff bla bla
{"ad_segments": [{"segment_offset": 123.45, "confidence": 0.7}]}. Note: Advertisements in the above podcast excerpt are identified with a moderate level of confidence due to their promotional nature, but not being from within the core content (i.e., discussing the movie or artwork) which suggests these segments could be a
"""
    assert clean_and_parse_model_output(model_outupt) == AdSegmentPredictionList(
        ad_segments=[
            AdSegmentPrediction(
                segment_offset=123.45,
                confidence=0.7,
            )
        ]
    )


def test_parse_multiple_segments_output() -> None:
    model_outupt = """
{"ad_segments": [
    {"segment_offset": 123.45, "confidence": 0.7},
    {"segment_offset": 23.45, "confidence": 0.8},
    {"segment_offset": 45.67, "confidence": 0.9}
]
}"""
    assert clean_and_parse_model_output(model_outupt) == AdSegmentPredictionList(
        ad_segments=[
            AdSegmentPrediction(segment_offset=123.45, confidence=0.7),
            AdSegmentPrediction(segment_offset=23.45, confidence=0.8),
            AdSegmentPrediction(segment_offset=45.67, confidence=0.9),
        ]
    )


def test_clean_parse_output_malformed() -> None:
    model_outupt = """
{"ad_segments": uhoh1.7, 1114.8, 1116.4, 1118.2, 1119.5, 1121.0, 1123.2, 1125.2], "confidence": 0.7}. Note: Advertisements in the above podcast excerpt are identified with a moderate level of confidence due to their promotional nature, but not being from within the core content (i.e., discussing the movie or artwork) which suggests these segments could be a
"""
    with pytest.raises(ValidationError):
        clean_and_parse_model_output(model_outupt)


def test_clean_parse_output_with_content_type() -> None:
    model_output = """
{"ad_segments": [{"segment_offset": 12.0, "confidence": 0.86}], "content_type": "promotional_external", "confidence": 0.91}
"""

    assert clean_and_parse_model_output(model_output) == AdSegmentPredictionList(
        ad_segments=[AdSegmentPrediction(segment_offset=12.0, confidence=0.86)],
        content_type="promotional_external",
        confidence=0.91,
    )


def test_clean_parse_output_truncated_missing_closing_brackets() -> None:
    """Test parsing truncated JSON missing closing ]} at the end."""
    model_output = '{"ad_segments":[{"segment_offset":10.5,"confidence":0.92}'
    result = clean_and_parse_model_output(model_output)
    assert result == AdSegmentPredictionList(
        ad_segments=[AdSegmentPrediction(segment_offset=10.5, confidence=0.92)]
    )


def test_clean_parse_output_truncated_multiple_segments() -> None:
    """Test parsing truncated JSON with multiple complete segments but missing closing."""
    model_output = '{"ad_segments":[{"segment_offset":10.5,"confidence":0.92},{"segment_offset":25.0,"confidence":0.85}'
    result = clean_and_parse_model_output(model_output)
    assert result == AdSegmentPredictionList(
        ad_segments=[
            AdSegmentPrediction(segment_offset=10.5, confidence=0.92),
            AdSegmentPrediction(segment_offset=25.0, confidence=0.85),
        ]
    )


def test_clean_parse_output_truncated_with_content_type() -> None:
    """Test parsing truncated JSON that includes content_type but is missing final }."""
    model_output = '{"ad_segments":[{"segment_offset":12.0,"confidence":0.86}],"content_type":"promotional_external","confidence":0.92'
    result = clean_and_parse_model_output(model_output)
    assert result == AdSegmentPredictionList(
        ad_segments=[AdSegmentPrediction(segment_offset=12.0, confidence=0.86)],
        content_type="promotional_external",
        confidence=0.92,
    )


def test_clean_parse_output_trailing_comma_is_stripped() -> None:
    """A JSON cut off right after a comma should drop the dangling comma and close."""
    model_output = '{"ad_segments":[{"segment_offset":10.5,"confidence":0.92},'
    result = clean_and_parse_model_output(model_output)
    assert result == AdSegmentPredictionList(
        ad_segments=[AdSegmentPrediction(segment_offset=10.5, confidence=0.92)]
    )


def test_clean_parse_output_strips_incomplete_trailing_key() -> None:
    """An object truncated right after a key's colon drops that incomplete pair."""
    model_output = '{"ad_segments":[],"content_type":'
    result = clean_and_parse_model_output(model_output)
    assert result == AdSegmentPredictionList(ad_segments=[])


def test_clean_parse_output_strips_incomplete_trailing_string_value() -> None:
    """An object truncated mid-string-value drops that incomplete pair."""
    model_output = '{"ad_segments":[],"content_type":"promotion'
    result = clean_and_parse_model_output(model_output)
    assert result == AdSegmentPredictionList(ad_segments=[])


def test_clean_parse_output_replaces_single_quotes() -> None:
    """Single-quoted JSON (some models emit it) is normalised to double quotes."""
    model_output = "{'ad_segments': []}"
    assert clean_and_parse_model_output(model_output) == AdSegmentPredictionList(
        ad_segments=[]
    )


def test_clean_parse_output_no_opening_brace_raises() -> None:
    with pytest.raises(AssertionError, match="No opening brace"):
        clean_and_parse_model_output("there is no json here at all")


def test_attempt_json_repair_returns_balanced_input_unchanged() -> None:
    balanced = '{"ad_segments": []}'
    assert _attempt_json_repair(balanced) == balanced
