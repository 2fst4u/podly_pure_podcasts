import pytest

from podcast_processor.cue_detector import CueDetector


@pytest.fixture
def detector() -> CueDetector:
    return CueDetector()


def test_has_cue_finds_urls(detector: CueDetector) -> None:
    assert detector.has_cue("Go to google.com today")
    assert not detector.has_cue("Just go search it")


def test_has_cue_finds_promos(detector: CueDetector) -> None:
    assert detector.has_cue("Use code podcast10")
    assert not detector.has_cue("I wrote some code")


def test_has_cue_finds_phones(detector: CueDetector) -> None:
    assert detector.has_cue("Call 1-800-555-1234")
    assert detector.has_cue("Number is 800-555-1234")
    assert not detector.has_cue("It cost 800 bucks")


def test_has_cue_finds_cta(detector: CueDetector) -> None:
    assert detector.has_cue("Sign up for a free trial")
    assert not detector.has_cue("I will sign this paper")


def test_analyze_finds_multiple_cues(detector: CueDetector) -> None:
    text = "Visit our site at example.com and use code save20. We'll be right back."
    result = detector.analyze(text)

    assert result["url"] is True
    assert result["promo"] is True
    assert result["transition"] is True
    assert result["phone"] is False
    assert result["self_promo"] is False


def test_highlight_cues_wraps_matches(detector: CueDetector) -> None:
    text = "Visit example.com today!"
    highlighted = detector.highlight_cues(text)

    assert "*** Visit ***" in highlighted
    assert "*** example.com ***" in highlighted


def test_highlight_cues_handles_no_matches(detector: CueDetector) -> None:
    text = "Just a normal sentence with no ads."
    assert detector.highlight_cues(text) == text


def test_highlight_cues_handles_overlapping_matches(detector: CueDetector) -> None:
    text = "Go to example.com to sign up"
    highlighted = detector.highlight_cues(text)

    assert "*** Go to ***" in highlighted
    assert "*** example.com ***" in highlighted
    assert "*** sign up ***" in highlighted
