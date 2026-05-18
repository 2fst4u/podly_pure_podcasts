import pytest

from app.models import Identification, TranscriptSegment
from podcast_processor.ad_merger import AdGroup, AdMerger


def test_ad_merger_should_merge_gap_and_confidence():
    merger = AdMerger()
    seg1 = TranscriptSegment(id=1, text="Hello", start_time=0.0, end_time=10.0)
    seg2 = TranscriptSegment(id=2, text="World", start_time=15.0, end_time=25.0)

    id1 = Identification(transcript_segment_id=1, confidence=0.85)
    id2 = Identification(transcript_segment_id=2, confidence=0.85)

    groups = merger.merge([seg1, seg2], [id1, id2], max_gap=2.0, min_content_gap=10.0)
    # Gap is 5 <= 10, confidence is >= 0.8
    assert len(groups) == 1
    assert groups[0].start_time == 0.0
    assert groups[0].end_time == 25.0


def test_ad_merger_is_valid_group_multiple_segments_low_confidence():
    merger = AdMerger()

    # multiple segments, duration > 10
    seg1 = TranscriptSegment(id=1, text="Normal", start_time=0.0, end_time=10.0)
    seg2 = TranscriptSegment(id=2, text="Text", start_time=12.0, end_time=20.0)
    id1 = Identification(transcript_segment_id=1, confidence=0.5)
    id2 = Identification(transcript_segment_id=2, confidence=0.5)

    groups = merger.merge([seg1, seg2], [id1, id2])
    # falls through to return True
    assert len(groups) == 1


def test_ad_merger_no_segments():
    merger = AdMerger()
    assert merger.merge([], []) == []


def test_ad_merger_extract_keywords_brands():
    merger = AdMerger()
    # Brands are capitalized words appearing 2+ times
    seg1 = TranscriptSegment(
        id=1, text="Drink Coca Cola and enjoy Coca Cola.", start_time=0.0, end_time=10.0
    )
    seg2 = TranscriptSegment(
        id=2, text="Call 555-123-4567 for more info.", start_time=10.0, end_time=20.0
    )

    id1 = Identification(transcript_segment_id=1, confidence=0.95)
    id2 = Identification(transcript_segment_id=2, confidence=0.95)

    groups = merger.merge([seg1, seg2], [id1, id2])
    assert len(groups) == 1
    assert "coca" in groups[0].keywords
    assert "cola" in groups[0].keywords
    assert "phone" in groups[0].keywords


def test_ad_merger_should_merge_gap_too_large():
    merger = AdMerger()
    seg1 = TranscriptSegment(id=1, text="Hello", start_time=0.0, end_time=10.0)
    seg2 = TranscriptSegment(id=2, text="World", start_time=25.0, end_time=35.0)

    id1 = Identification(transcript_segment_id=1, confidence=0.95)
    id2 = Identification(transcript_segment_id=2, confidence=0.95)

    groups = merger.merge([seg1, seg2], [id1, id2], max_gap=2.0, min_content_gap=10.0)
    # Gap is 15 > 10, should not merge
    assert len(groups) == 2


def test_ad_merger_should_merge_shared_keywords():
    merger = AdMerger()
    seg1 = TranscriptSegment(
        id=1, text="Visit examplesite.com", start_time=0.0, end_time=10.0
    )
    seg2 = TranscriptSegment(
        id=2, text="Go to examplesite.com today", start_time=25.0, end_time=35.0
    )
    id1 = Identification(transcript_segment_id=1, confidence=0.5)
    id2 = Identification(transcript_segment_id=2, confidence=0.5)

    groups = merger.merge([seg1, seg2], [id1, id2], max_gap=2.0, min_content_gap=20.0)
    assert len(groups) == 1
    assert groups[0].start_time == 0.0
    assert groups[0].end_time == 35.0
    assert "examplesite.com" in groups[0].keywords


def test_ad_merger_filter_weak_groups():
    merger = AdMerger()

    # Duration > 180.0, no keywords, low confidence
    seg1 = TranscriptSegment(
        id=1, text="Normal text without keywords", start_time=0.0, end_time=200.0
    )
    id1 = Identification(transcript_segment_id=1, confidence=0.5)

    groups = merger.merge([seg1], [id1])
    assert len(groups) == 0


def test_ad_merger_is_valid_group_short():
    merger = AdMerger()

    # short duration <= 10.0, no keywords, low confidence
    seg1 = TranscriptSegment(id=1, text="Normal", start_time=0.0, end_time=5.0)
    id1 = Identification(transcript_segment_id=1, confidence=0.5)

    groups = merger.merge([seg1], [id1])
    assert len(groups) == 0


def test_ad_merger_high_confidence():
    merger = AdMerger()

    # High confidence >= 0.9 for both, low confidence for 3rd segment
    seg1 = TranscriptSegment(id=1, text="Normal", start_time=0.0, end_time=5.0)
    seg2 = TranscriptSegment(id=2, text="Text", start_time=6.0, end_time=10.0)

    id1 = Identification(transcript_segment_id=1, confidence=0.95)
    id2 = Identification(transcript_segment_id=2, confidence=0.95)

    groups = merger.merge([seg1, seg2], [id1, id2], max_gap=2.0, min_content_gap=10.0)
    assert len(groups) == 1
    assert groups[0].start_time == 0.0
    assert groups[0].end_time == 10.0
