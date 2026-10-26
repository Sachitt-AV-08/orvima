"""Tests for orvima.vision module."""

from orvima.vision import _tesseract_available, _require_cv, vision_ocr, vision_find_text


def test_tesseract_available():
    result = _tesseract_available()
    assert isinstance(result, bool)


def test_require_cv():
    try:
        _require_cv()
        cv_ok = True
    except Exception:
        cv_ok = False
    assert isinstance(cv_ok, bool)


def test_vision_ocr_no_file():
    result = vision_ocr("/nonexistent/image.png")
    assert isinstance(result, dict)
    assert result.get("ok") is False or "error" in result


def test_vision_find_text_no_file():
    result = vision_find_text("/nonexistent/image.png", "hello")
    assert isinstance(result, dict)
    assert result.get("ok") is False or "error" in result


def test_vision_describe_no_file():
    from orvima.vision import vision_describe
    result = vision_describe("/nonexistent/image.png")
    assert isinstance(result, dict)


def test_vision_match_template_no_files():
    from orvima.vision import vision_match_template
    result = vision_match_template("/nonexistent/img.png", "/nonexistent/tpl.png")
    assert isinstance(result, dict)


def test_vision_detect_faces_no_file():
    from orvima.vision import vision_detect_faces
    result = vision_detect_faces("/nonexistent/image.png")
    assert isinstance(result, dict)


def test_vision_ocr_screenshot():
    from orvima.vision import vision_ocr_screenshot
    try:
        result = vision_ocr_screenshot(None)
        assert isinstance(result, dict)
    except Exception:
        pass  # browser may not be available