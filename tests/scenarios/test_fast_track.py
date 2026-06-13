"""Fast track routing validation."""

from app.ai.schemas import AIClusterOutput
from app.publisher.tracks import route_track


class FakeSession:
    def scalar(self, q):
        return 0


def test_fast_track_all_conditions_met():
    result = AIClusterOutput(
        status="publish",
        editorial_priority=5,
        confidence=0.90,
        headline="تیتر فوری",
        summary="خلاصه",
        why_it_matters="",
        sensitivity="normal",
    )
    track = route_track(FakeSession(), result, independent_source_count=2)
    assert track == "fast"


def test_fast_blocked_by_conflicts():
    result = AIClusterOutput(
        status="publish",
        editorial_priority=5,
        confidence=0.90,
        headline="تیتر",
        summary="خلاصه",
        why_it_matters="",
        conflicts=["اختلاف روایت"],
        sensitivity="normal",
    )
    track = route_track(FakeSession(), result, independent_source_count=2)
    assert track == "batch"
