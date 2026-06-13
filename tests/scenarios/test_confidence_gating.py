"""Fast/Batch confidence gating."""

from app.ai.schemas import AIClusterOutput
from app.publisher.tracks import route_track


class FakeSession:
    def scalar(self, q):
        return 0


def test_fast_downgrade_to_batch():
    result = AIClusterOutput(
        status="publish",
        editorial_priority=4,
        confidence=0.80,
        headline="تیتر",
        summary="خلاصه",
        why_it_matters="",
        sensitivity="normal",
    )
    track = route_track(FakeSession(), result, independent_source_count=2)
    assert track == "batch"


def test_fast_track_requires_priority_5():
    result = AIClusterOutput(
        status="publish",
        editorial_priority=5,
        confidence=0.80,
        headline="تیتر",
        summary="خلاصه",
        why_it_matters="",
        sensitivity="normal",
    )
    track = route_track(FakeSession(), result, independent_source_count=2)
    assert track == "fast"


def test_reject_low_confidence():
    result = AIClusterOutput(
        status="publish",
        editorial_priority=3,
        confidence=0.30,
        headline="تیتر",
        summary="خلاصه",
        why_it_matters="",
        sensitivity="normal",
    )
    track = route_track(FakeSession(), result, independent_source_count=2)
    assert track == "reject"
