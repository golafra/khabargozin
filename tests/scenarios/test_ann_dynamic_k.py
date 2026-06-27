"""ANN top_k dynamic configuration."""

from unittest.mock import MagicMock, patch

from app.clustering.ann_config import ann_top_k


def test_breaking_uses_higher_top_k():
    session = MagicMock()
    session.scalar.return_value = 5
    with patch("app.clustering.ann_config.get_settings") as mock_settings:
        mock_settings.return_value.ANN_TOP_K_BREAKING = 20
        mock_settings.return_value.ANN_TOP_K_DEFAULT = 10
        mock_settings.return_value.ANN_TOP_K_MIN = 8
        k = ann_top_k(session, "breaking", "earthquake")
    assert k == 20
