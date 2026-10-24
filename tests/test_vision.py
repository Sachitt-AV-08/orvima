"""Pins orvima.vision tool behavior (local, no network)."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from orvima import vision


def _text_image(path: Path, text: str = "HELLO ORVIMA 123") -> Path:
    img = Image.new("RGB", (420, 120), "white")
    d = ImageDraw.Draw(img)
    d.text((20, 30), text, fill="black")
    img.save(path)
    return path


def _scene_template(tmp_path):
    scene = Image.new("RGB", (240, 120), "white")
    d = ImageDraw.Draw(scene)
    d.rectangle((40, 30, 80, 70), fill="black")
    scene_path = tmp_path / "scene.png"
    scene.save(scene_path)
    tmpl = scene.crop((40, 30, 80, 70))
    tmpl_path = tmp_path / "tmpl.png"
    tmpl.save(tmpl_path)
    return scene_path, tmpl_path


def test_vision_ocr_happy(tmp_path):
    img = _text_image(tmp_path / "ocr.png")
    res = vision.vision_ocr(str(img))
    assert res["ok"] is True
    assert res["word_count"] >= 1
    assert "text" in res
    assert res["confidence"] >= 0


def test_vision_ocr_missing_file():
    res = vision.vision_ocr("/no/such/file.png")
    assert res["ok"] is False
    assert "not found" in res["error"] or "image not found" in res["error"]


def test_vision_ocr_detail_toggle(tmp_path):
    img = _text_image(tmp_path / "ocr.png")
    res = vision.vision_ocr(str(img), detail=False)
    assert res["ok"] is True
    assert "boxes" not in res
    res2 = vision.vision_ocr(str(img), detail=True)
    assert "boxes" in res2


def test_vision_ocr_region(tmp_path):
    img = _text_image(tmp_path / "ocr.png")
    res = vision.vision_ocr_region(str(img), 0, 0, 100, 50)
    assert isinstance(res, dict)
    # region clamped; ok depends on tesseract but should be dict with ok key
    assert "ok" in res


def test_vision_find_text(tmp_path):
    img = _text_image(tmp_path / "ocr.png", text="HELLO")
    res = vision.vision_find_text(str(img), "HELLO")
    assert res["ok"] is True
    assert res["found"] is True
    res2 = vision.vision_find_text(str(img), "zzzzzz")
    assert res2["ok"] is True
    assert res2["found"] is False


def test_vision_describe(tmp_path):
    img = _text_image(tmp_path / "d.png")
    res = vision.vision_describe(str(img))
    assert res["ok"] is True
    assert res["width"] == 420
    assert res["height"] == 120
    assert "dominant_colors" in res
    assert "complexity" in res


def test_vision_match_template(tmp_path):
    scene_path, tmpl_path = _scene_template(tmp_path)
    res = vision.vision_match_template(str(scene_path), str(tmpl_path), threshold=0.5)
    assert res["ok"] is True
    assert res["matched"] is True
    assert res["match_count"] >= 1


def test_vision_match_template_larger_template(tmp_path):
    scene_path, tmpl_path = _scene_template(tmp_path)
    # template larger than scene -> error
    res = vision.vision_match_template(str(tmpl_path), str(scene_path))
    assert res["ok"] is False
    assert "larger" in res["error"]


def test_vision_detect_faces_no_faces(tmp_path):
    img = _text_image(tmp_path / "f.png")
    res = vision.vision_detect_faces(str(img))
    # Haar cascade available; result ok even if zero faces
    assert isinstance(res, dict)
    assert "ok" in res
    if res["ok"]:
        assert res["face_count"] >= 0


def test_vision_detect_faces_missing_file():
    res = vision.vision_detect_faces("/no/such.png")
    assert res["ok"] is False


def test_vision_video_frames_missing_file():
    res = vision.vision_video_frames("/no/such/video.mp4")
    assert res["ok"] is False


def test_vision_compare_ocr(tmp_path):
    img = _text_image(tmp_path / "c.png")
    res = vision.vision_compare_ocr(str(img))
    assert res["ok"] is True
    assert "rotation_deg" in res
    assert "all_attempts" in res


def test_vision_ocr_screenshot_missing_bytes():
    class FakeBrowser:
        def screenshot(self):
            return {"url": "http://example.com", "foo": 1}
    res = vision.vision_ocr_screenshot(FakeBrowser())
    assert res["ok"] is False

def test_vision_ocr_screenshot_exception():
    class FakeBrowser:
        def screenshot(self):
            raise RuntimeError("boom")
    res = vision.vision_ocr_screenshot(FakeBrowser())
    assert res["ok"] is False
    assert "boom" in res["error"]

def test_vision_ocr_screenshot_success(monkeypatch, tmp_path):
    # Build a browser screenshot payload with base64 image
    import base64
    import io
    _text_image(tmp_path / "s.png")
    img = Image.open(tmp_path / "s.png")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    class FakeBrowser:
        def screenshot(self):
            return {"png_b64": b64, "url": "http://x"}
    res = vision.vision_ocr_screenshot(FakeBrowser())
    assert res["ok"] is True
    assert "text" in res

def test_vision_video_ocr_missing():
    res = vision.vision_video_ocr("/no/such.mp4")
    assert res["ok"] is False

def test_vision_video_scene_changes_missing():
    res = vision.vision_video_scene_changes("/no/such.mp4")
    assert res["ok"] is False

def test_vision_tools_tuples():
    assert len(vision.VISION_TOOLS) == len(vision.VISION_TOOLS_SIMPLE) + len(vision.VISION_TOOLS_BROWSER)
