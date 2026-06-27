"""Lineage — republish counts as one independent source."""

from unittest.mock import patch

from app.clustering.lineage import recalculate_independent_sources


def test_republisher_not_independent():
    """sim>0.95 with primary → one lineage."""

    class FakeMsg:
        def __init__(self, text, source_id, is_primary=False):
            self.text = text
            self.source_id = source_id
            self.is_deleted = False
            self.is_primary_source = is_primary
            self.raw_payload = {}

    class FakeSrc:
        def __init__(self, id, is_primary):
            self.id = id
            self.is_primary_source = is_primary
            self.credibility_weight = 1.0

    rows = [
        (FakeMsg("خبر مهم درباره زلزله", 1, True), FakeSrc(1, True)),
        (FakeMsg("خبر مهم درباره زلزله", 2, False), FakeSrc(2, False)),
    ]

    class FakeSession:
        def execute(self, q):
            class R:
                def all(inner):
                    return rows
            return R()

    with patch("app.clustering.lineage.text_similarity", return_value=0.98):
        count = recalculate_independent_sources(FakeSession(), 1)
    assert count == 1
