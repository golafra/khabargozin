"""Media filter."""

from app.fetcher.media_filter import extract_media_meta, is_media_acceptable


def test_video_too_long_rejected():
    meta = {"type": "video", "duration": 120, "width": 320, "height": 240}
    assert is_media_acceptable(meta) is False


def test_normal_photo_accepted():
    meta = {"type": "photo", "width": 800, "height": 600}
    assert is_media_acceptable(meta) is True


def test_extract_photo_meta():
    media = {
        "_": "messageMediaPhoto",
        "photo": {"sizes": [{"_": "photoSize", "w": 800, "h": 600}]},
    }
    meta = extract_media_meta(media)
    assert meta["type"] == "photo"
    assert meta["width"] == 800
