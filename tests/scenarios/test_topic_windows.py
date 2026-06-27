"""Topic window configuration."""

from app.clustering.topic_windows import active_window_minutes, reconcile_lookback_hours


def test_election_window_14_days():
    assert active_window_minutes("election") == 14 * 24 * 60
    assert reconcile_lookback_hours("election") == 14 * 24


def test_earthquake_window_24h():
    assert active_window_minutes("earthquake") == 24 * 60
    assert reconcile_lookback_hours("earthquake") == 24


def test_war_window_30_days():
    assert reconcile_lookback_hours("war") == 30 * 24
