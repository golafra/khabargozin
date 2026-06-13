"""Hold AI re-run — phase 2."""

from app.db.models.cluster import Cluster
from app.publisher.hold import needs_ai_rerun


def test_rerun_when_independent_count_changes():
    c = Cluster(ai_independent_source_count_at_run=1, independent_source_count=2)
    assert needs_ai_rerun(c, 2) is True


def test_no_rerun_same_count():
    c = Cluster(ai_independent_source_count_at_run=2)
    assert needs_ai_rerun(c, 2) is False
