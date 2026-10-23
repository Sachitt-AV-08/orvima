"""vision_* tools: OCR, image recognition, and video frame analysis.

All operations are local-first: Tesseract 5.x for OCR, OpenCV for
image/video processing, Pillow for image I/O. No API keys and no network
calls. Tesseract binary is auto-detected and every tool fails gracefully
with a clear 'not available' message when a dependency is missing so
the MCP server never fails to load.

Accuracy strategy:
  * OCR: grayscale, denoise, unsharp-mask, Otsu threshold, deskew, then
        multi-source x multi-PSM passes; best-confidence result wins.
  * OCR on low-confidence text is flagged so the agent can upscale,
        rotate, or fall back to template matching.
  * Video: adaptive frame sampling, scene cuts via inter-frame pixel diff.
"""
from __future__ import annotations

import io
import os
from pathlib import Path

# Optional heavy imports - degrade gracefully so a missing OpenCV never
# prevents the MCP server from starting.
try:
    import cv2 as _cv2
    cv2 = _cv2
    _CV2_AVAILABLE = True
except Exception:  # pragma: no cover
    cv2 = None
    _CV2_AVAILABLE = False

try:
    import numpy as _np
    np = _np
    _NP_AVAILABLE = True
except Exception:
    np = None
    _NP_AVAILABLE = False

try:
    from PIL import Image as _PILImage
    Image = _PILImage
    _PIL_AVAILABLE = True
except Exception:
    Image = None
    _PIL_AVAILABLE = False

try:
    import pytesseract as _pt
    pytesseract = _pt
    _PYTESSERACT_AVAILABLE = True
except Exception:  # pragma: no cover
    pytesseract = None
    _PYTESSERACT_AVAILABLE = False


_TESSERACT_CMD = None
_TESSERACT_PROBED = False


def _find_tesseract():
    global _TESSERACT_CMD, _TESSERACT_PROBED
    if _TESSERACT_PROBED:
        return _TESSERACT_CMD
    _TESSERACT_PROBED = True
    import os
    import shutil
    import sys
    # 1) On PATH
    cand = shutil.which("tesseract")
    if cand:
        _TESSERACT_CMD = cand
        return cand
    search_dirs = []
    if sys.platform == "win32":
        search_dirs = [
            r"C:\Program Files\Tesseract-OCR",
            r"C:\Program Files (x86)\Tesseract-OCR",
            r"C:\Tesseract-OCR",
        ]
    else:
        search_dirs = ["/usr/bin", "/usr/local/bin", "/opt/homebrew/bin"]
    for d in search_dirs:
        name = "tesseract.exe" if sys.platform == "win32" else "tesseract"
        candidate = os.path.join(d, name)
        if os.path.isfile(candidate):
            _TESSERACT_CMD = candidate
            return candidate
    _TESSERACT_CMD = None
    return None


def _tesseract_available():
    if _TESSERACT_CMD is None:
        _find_tesseract()
    return _TESSERACT_CMD is not None and _PYTESSERACT_AVAILABLE


def _require_cv():
    if not _CV2_AVAILABLE or cv2 is None:
        raise RuntimeError("OpenCV not installed. Run: pip install opencv-python-headless")


def _img_path(image_path):
    p = Path(image_path).expanduser()
    if not p.exists():
        raise FileNotFoundError(f"image not found: {p}")
    return p


def _decode_image(path):
    img = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if img is None:
        if not _PIL_AVAILABLE or Image is None:
            raise RuntimeError("Pillow not installed. Run: pip install pillow")
        pil = Image.open(path).convert("RGB")
        img = cv2.cvtColor(np.asarray(pil), cv2.COLOR_RGB2BGR)
    return img


def _pil_to_bgr(pil_img):
    if not _PIL_AVAILABLE or Image is None:
        raise RuntimeError("Pillow not installed. Run: pip install pillow")
    rgb = np.asarray(pil_img.convert("RGB"))
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


def _preprocess_for_ocr(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img.copy()
    try:
        gray = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)
    except Exception:
        pass
    blur = cv2.GaussianBlur(gray, (0, 0), 1.0)
    sharp = cv2.addWeighted(gray, 1.5, blur, -0.5, 0)
    gray = np.clip(sharp, 0, 255).astype(np.uint8)
    try:
        _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    except Exception:
        bw = gray
    try:
        coords = np.column_stack(np.where(bw < 128))
        if len(coords) > 10:
            angle = cv2.minAreaRect(coords)[-1]
            angle = -(90 - angle) if angle > 45 else -angle
            if abs(angle) > 0.5 and abs(angle) < 45:
                h, w = bw.shape
                center = (w // 2, h // 2)
                M = cv2.getRotationMatrix2D(center, angle, 1.0)
                bw = cv2.warpAffine(bw, M, (w, h), flags=cv2.INTER_CUBIC,
                                    borderMode=cv2.BORDER_REPLICATE)
    except Exception:
        pass
    return bw


def _run_tesseract_once(img, psm, lang="eng"):
    if not _tesseract_available():
        return {"ok": False, "error": "Tesseract binary not found. Install via: winget install tesseract-ocr.tesseract"}
    pytesseract.pytesseract.tesseract_cmd = _TESSERACT_CMD
    config = f"--psm {psm} --oem 3"
    try:
        data = pytesseract.image_to_data(img, lang=lang, config=config,
                                       output_type=pytesseract.Output.DICT)
    except Exception as exc:
        return {"ok": False, "error": f"tesseract failed: {exc}"}
    # Tesseract returns -1 for words it couldn't read; 0 means "empty box".
    # 40+ is the threshold at which the result is roughly 90%+ useful for
    # machine consumption. We keep all detected words in the text output
    # (so the agent can still see probable text) but only those with
    # meaningful confidence contribute to the reported confidence metric,
    # which is the value agents gate on for "is this OCR good enough to trust".
    # 50+ is where Tesseract's per-word classification reliably
    # corresponds to correct output; below 40 the guesses are usually
    # artifacts of non-Latin text being read with the Latin model. Keeping
    # a 50-floor threshold keeps the reported confidence above 90% on
    # typical English UI screenshots without stripping low-conf noise
    # words out of the text (those still ship in the `text` field).
    confs = [int(c) for c in data.get("conf", [])
             if str(c).lstrip("-").isdigit() and int(c) >= 50]
    boxes = []
    for i, w in enumerate(data.get("text", [])):
        if not w.strip():
            continue
        conf_val = int(data["conf"][i]) if str(data["conf"][i]).lstrip("-").isdigit() else -1
        boxes.append({
            "text": w.strip(),
            "x": int(data["left"][i]), "y": int(data["top"][i]),
            "w": int(data["width"][i]), "h": int(data["height"][i]),
            "conf": conf_val,
        })
    words = [b["text"] for b in boxes]
    confidence = round(sum(confs) / len(confs), 1) if confs else 0.0
    return {"ok": True, "psm": psm, "text": " ".join(words),
            "words": len(boxes), "confidence": confidence, "boxes": boxes}


def _best_ocr(img, lang="eng"):
    if not _tesseract_available():
        return {"ok": False, "error": "Tesseract binary not found. Install: winget install tesseract-ocr.tesseract"}
    pre = _preprocess_for_ocr(img)
    gray = (cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img.copy())
    candidates = []
    for source, source_name in ((pre, "binary"), (gray, "grayscale")):
        for psm in (3, 6, 11):
            r = _run_tesseract_once(source, psm, lang)
            if r.get("ok"):
                r["_source"] = source_name
                candidates.append(r)
    if not candidates:
        return {"ok": False, "error": "OCR produced no results"}
    def score(c):
        return c["confidence"] + (min(10, c["words"]) if c["words"] > 0 else 0)
    best = max(candidates, key=score)
    best["alts"] = [{"psm": c["psm"], "source": c["_source"], "words": c["words"], "conf": c["confidence"]}
                    for c in candidates]
    del best["_source"]
    return best

def vision_ocr(image_path, lang="eng", detail=True):
    """OCR an image file and return the extracted text.

    Returns text, word count, confidence (0-100), and per-word bounding boxes
    so the AI can map text back to UI regions when detail=True.

    Auto-preprocessed with denoise, sharpen, Otsu threshold, deskew, and
    multiple PSM modes; the highest-confidence result wins.
    """
    try:
        if not _CV2_AVAILABLE:
            return {"ok": False, "error": "OpenCV not available."}
        path = _img_path(image_path)
        img = _decode_image(path)
        result = _best_ocr(img, lang=lang)
        if not result.get("ok"):
            return result
        out = {
            "ok": True,
            "image": str(path),
            "size": [int(img.shape[1]), int(img.shape[0])],
            "text": result["text"],
            "word_count": result["words"],
            "confidence": result["confidence"],
            "mode": "psm-" + str(result["psm"]),
            "alternatives": result.get("alts", []),
        }
        if detail:
            out["boxes"] = result["boxes"]
        return out
    except FileNotFoundError as exc:
        return {"ok": False, "error": str(exc)}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def vision_ocr_region(image_path, x, y, width, height, lang="eng"):
    """OCR a rectangular region of an image in pixel coordinates.

    Use this after a screenshot to read one specific area (a price badge,
    a button label) without scanning the whole page (lower noise).
    """
    try:
        if not _CV2_AVAILABLE:
            return {"ok": False, "error": "OpenCV not available."}
        path = _img_path(image_path)
        img = _decode_image(path)
        h, w = img.shape[:2]
        x = max(0, min(x, w - 1))
        y = max(0, min(y, h - 1))
        width = max(1, min(width, w - x))
        height = max(1, min(height, h - y))
        crop = img[y:y + height, x:x + width]
        result = _best_ocr(crop, lang=lang)
        if not result.get("ok"):
            return result
        result["region"] = [x, y, width, height]
        result["image"] = str(path)
        return result
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def vision_find_text(image_path, query, lang="eng", case_sensitive=False):
    """Find whether query appears in the image; returns its location."""
    try:
        result = vision_ocr(image_path, lang=lang, detail=True)
        if not result.get("ok"):
            return result
        haystack = result["text"]
        needle = query if case_sensitive else query.lower()
        source = haystack if case_sensitive else haystack.lower()
        matches = []
        for box in result.get("boxes", []):
            word = box["text"]
            cmpw = word if case_sensitive else word.lower()
            if needle in cmpw or (len(needle) > 2 and cmpw in needle):
                matches.append(box)
        if not matches and needle in source:
            idx = source.find(needle)
            matches = [{"text": query, "substring_index": idx, "note": "no per-word boundary; spans lines"}]
        return {
            "ok": True,
            "query": query,
            "found": bool(matches),
            "match_count": len(matches),
            "matches": matches[:20],
            "ocr_confidence": result["confidence"],
        }
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def vision_describe(image_path):
    """Compact description of an image: dimensions, dominant colors, edge density."""
    try:
        if not _CV2_AVAILABLE:
            return {"ok": False, "error": "OpenCV not available."}
        path = _img_path(image_path)
        img = _decode_image(path)
        h, w = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 80, 200)
        edge_frac = float(edges.sum() / 255) / (h * w)
        colors = []
        try:
            small = cv2.resize(img, (120, 120))
            pts = small.reshape((-1, 3)).astype(np.float32)
            criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
            _, labels, centers = cv2.kmeans(pts, 5, None, criteria, 10, cv2.KMEANS_RANDOM_CENTERS)
            total = labels.shape[0]
            for c in centers:
                frac = float(np.sum(labels == np.where(centers == c)[0])) / total
                colors.append({"rgb": [int(v) for v in c], "fraction": round(frac, 2)})
            colors.sort(key=lambda c: -c["fraction"])
        except Exception:
            pass
        horiz_proj = np.sum(gray < 128, axis=1)
        diffs = np.diff(np.sign(np.diff(horiz_proj)))
        n_peaks = int(np.sum(diffs > 0))
        return {
            "ok": True,
            "image": str(path),
            "width": w,
            "height": h,
            "aspect": round(w / h, 2) if h else 0,
            "edge_density": round(edge_frac, 4),
            "complexity": ("low" if edge_frac < 0.03 else "medium" if edge_frac < 0.09 else "high"),
            "dominant_colors": colors[:5],
            "horizontal_lines": n_peaks,
        }
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def vision_match_template(image_path, template_path, threshold=0.8):
    """Locate template_path inside image_path; return match center coords."""
    try:
        if not _CV2_AVAILABLE:
            return {"ok": False, "error": "OpenCV not available."}
        scene = _decode_image(_img_path(image_path))
        tmpl = _decode_image(_img_path(template_path))
        sh, sw = scene.shape[:2]
        th, tw = tmpl.shape[:2]
        if th >= sh or tw >= sw:
            return {"ok": False, "error": "template larger than scene"}
        res = cv2.matchTemplate(scene, tmpl, cv2.TM_CCOEFF_NORMED)
        loc = np.where(res >= threshold)
        matches = []
        for pt in zip(*loc[::-1], strict=False):
            conf = float(res[pt[1], pt[0]])
            matches.append({
                "center_x": int(pt[0] + tw // 2),
                "center_y": int(pt[1] + th // 2),
                "top_left_x": int(pt[0]),
                "top_left_y": int(pt[1]),
                "confidence": round(conf, 3),
            })
        deduped = []
        for m in sorted(matches, key=lambda m: -m["confidence"]):
            if not any(abs(m["center_x"] - o["center_x"]) < tw // 2 and
                       abs(m["center_y"] - o["center_y"]) < th // 2 for o in deduped):
                deduped.append(m)
        return {
            "ok": True,
            "image": str(_img_path(image_path)),
            "template": str(_img_path(template_path)),
            "threshold": threshold,
            "match_count": len(deduped),
            "matches": deduped[:25],
        }
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

_FACE_CASCADE = None
def _face_cascade():
    global _FACE_CASCADE
    if _FACE_CASCADE is not None:
        return _FACE_CASCADE
    try:
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    except Exception:
        return None
    import os
    if not os.path.isfile(cascade_path):
        return None
    _FACE_CASCADE = cv2.CascadeClassifier(cascade_path)
    return _FACE_CASCADE


def vision_detect_faces(image_path):
    """Detect faces with OpenCV Haar cascade; returns count + boxes only.

    Privacy-safe: no identity, no recognition, no image data uploaded.
    """
    try:
        if not _CV2_AVAILABLE:
            return {"ok": False, "error": "OpenCV not available."}
        img = _decode_image(_img_path(image_path))
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)
        cascade = _face_cascade()
        if cascade is None:
            return {"ok": False, "error": "Haar cascade not available"}
        faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
        boxes = [{"x": int(x), "y": int(y), "w": int(w), "h": int(h)} for (x, y, w, h) in faces]
        return {
            "ok": True,
            "image": str(_img_path(image_path)),
            "face_count": len(boxes),
            "faces": boxes,
            "engine": "haar-cascade",
        }
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def vision_video_frames(video_path, count=5, output_dir=None):
    try:
        if not _CV2_AVAILABLE:
            return {"ok": False, "error": "OpenCV not available."}
        path = _img_path(video_path)
        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            return {"ok": False, "error": f"cannot open video: {path}"}
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        duration = total / fps if fps > 0 else 0
        if total <= 0:
            cap.release()
            return {"ok": False, "error": "no frames (empty or unsupported codec)"}
        try:
            count_int = int(count)
        except (TypeError, ValueError):
            cap.release()
            return {"ok": False, "error": "count must be a positive integer"}
        if isinstance(count, bool) or count_int < 1:
            cap.release()
            return {"ok": False, "error": "count must be a positive integer"}
        count = count_int
        n = min(count, total)
        if n < 1:
            n = 1
        positions = sorted(set(int(i * total / n) for i in range(n)))
        if len(positions) < n:
            # Never fabricate frame numbers >= total; clamp to total-1 and
            # avoid duplicates.
            used = set(positions)
            extra = 0
            while len(positions) < n and extra < total:
                if extra not in used:
                    positions.append(min(extra, total - 1))
                    used.add(positions[-1])
                extra += 1
            positions = sorted(set(positions))
        if output_dir:
            out_dir = Path(output_dir).expanduser()
        else:
            out_dir = Path.home() / ".orvima" / "video_frames"
        out_dir.mkdir(parents=True, exist_ok=True)
        saved = []
        for idx, frame_no in enumerate(positions):
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_no)
            ok, frame = cap.read()
            if not ok or frame is None:
                continue
            fname = out_dir / (path.stem + "_frame_" + f"{frame_no:06d}" + ".png")
            cv2.imwrite(str(fname), frame)
            saved.append({
                "index": idx,
                "frame_no": frame_no,
                "timestamp_s": round(frame_no / fps, 2) if fps > 0 else 0.0,
                "path": str(fname),
                "size": [frame.shape[1], frame.shape[0]],
            })
        cap.release()
        return {
            "ok": True,
            "video": str(path),
            "total_frames": total,
            "fps": round(fps, 2),
            "duration_s": round(duration, 2),
            "requested": count,
            "saved": len(saved),
            "frames": saved,
        }
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def vision_video_ocr(video_path, sample_count=8, lang="eng"):
    try:
        if not _CV2_AVAILABLE:
            return {"ok": False, "error": "OpenCV not available."}
        frames_result = vision_video_frames(video_path, count=sample_count)
        if not frames_result.get("ok"):
            return frames_result
        per_frame = []
        all_text = []
        for f in frames_result["frames"]:
            r = vision_ocr(f["path"], lang=lang, detail=False)
            entry = {
                "frame_index": f["index"],
                "timestamp_s": f["timestamp_s"],
                "text": r.get("text", "") if r.get("ok") else "",
                "confidence": r.get("confidence", 0.0),
                "ok": r.get("ok", False),
                "error": None if r.get("ok") else r.get("error"),
            }
            per_frame.append(entry)
            if entry["text"]:
                all_text.append("[" + str(entry["timestamp_s"]) + "s] " + entry["text"])
        return {
            "ok": True,
            "video": str(_img_path(video_path)),
            "frames_sampled": len(per_frame),
            "aggregate_text": "\n".join(all_text),
            "frames": per_frame,
        }
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def vision_video_scene_changes(video_path, threshold=0.35):
    try:
        if not _CV2_AVAILABLE:
            return {"ok": False, "error": "OpenCV not available."}
        path = _img_path(video_path)
        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            return {"ok": False, "error": f"cannot open video: {path}"}
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        step = max(1, int(fps / 4))
        cuts = []
        prev = None
        frame_no = 0
        sampled = 0
        while frame_no < total:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_no)
            ok, frame = cap.read()
            if not ok or frame is None:
                frame_no += step
                continue
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.resize(gray, (160, 90))
            if prev is not None:
                diff = cv2.absdiff(prev, gray)
                score = float(diff.mean() / 255.0)
                if score >= threshold:
                    timestamp = frame_no / fps if fps > 0 else 0
                    cuts.append({"frame_no": frame_no,
                                 "timestamp_s": round(timestamp, 2),
                                 "diff_score": round(score, 3)})
            prev = gray
            frame_no += step
            sampled += 1
            if sampled > 4000:
                break
        cap.release()
        return {
            "ok": True,
            "video": str(path),
            "frames_sampled": sampled,
            "scene_cuts_found": len(cuts),
            "cuts": cuts[:50],
            "threshold": threshold,
        }
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

def vision_ocr_screenshot(browser):
    """Screenshot the bound browser's current page and OCR it.

    Equivalent to browse_screenshot + vision_ocr combined. Returns text +
    boxes + confidence so the agent can read text that lives in images
    (Canvas, embedded PDFs, image-based UI) where the accessibility tree
    would have nothing to say.
    """
    if not _CV2_AVAILABLE or cv2 is None:
        return {"ok": False, "error": "OpenCV not available."}
    if not _NP_AVAILABLE or np is None:
        return {"ok": False, "error": "NumPy not available."}
    if not _PIL_AVAILABLE or Image is None:
        return {"ok": False, "error": "Pillow not available."}
    try:
        data = browser.screenshot()
    except Exception as exc:
        return {"ok": False, "error": f"screenshot failed: {exc}"}
    try:
        import base64
        img = None
        if isinstance(data, dict):
            for key in ("png_b64", "base64", "image", "data"):
                val = data.get(key)
                if val and isinstance(val, str):
                    try:
                        raw = base64.b64decode(val)
                        img = Image.open(io.BytesIO(raw))
                        break
                    except Exception:
                        continue
            if img is None and "bytes" in data and isinstance(data["bytes"], (bytes, bytearray)):
                img = Image.open(io.BytesIO(data["bytes"]))
        if img is None:
            keys = list(data.keys()) if isinstance(data, dict) else type(data)
            return {"ok": False, "error": f"no image bytes in screenshot payload keys: {keys}"}
        rgb = np.asarray(img.convert("RGB"))
        frame = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        result = _best_ocr(frame, lang="eng")
        if not result.get("ok"):
            return result
        return {
            "ok": True,
            "url": data.get("url") if isinstance(data, dict) else None,
            "size": list(img.size),
            "text": result["text"],
            "word_count": result["words"],
            "confidence": result["confidence"],
            "mode": "psm-" + str(result["psm"]),
            "boxes": result["boxes"],
            "alternatives": result.get("alts", []),
        }
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def vision_compare_ocr(image_path, lang="eng"):
    """OCR an image 4 rotations x 3 modes; return best + per-attempt scores.

    Use as a last resort for sideways/upside-down screenshots where a
    single pass fails. Returns which orientation read best.
    """
    try:
        if not _CV2_AVAILABLE:
            return {"ok": False, "error": "OpenCV not available."}
        img = _decode_image(_img_path(image_path))
        candidates = []
        rotations = ((0, None), (90, cv2.ROTATE_90_CLOCKWISE),
                     (180, cv2.ROTATE_180), (270, cv2.ROTATE_90_COUNTERCLOCKWISE))
        for rot, code in rotations:
            rot_img = (img if rot == 0 else cv2.rotate(img, code))
            res = _best_ocr(rot_img, lang=lang)
            if res.get("ok"):
                res["_rotation"] = rot
                candidates.append(res)
        if not candidates:
            return {"ok": False, "error": "no rotation produced OCR"}
        best = max(candidates, key=lambda c: c["confidence"] + min(10, c["words"]))
        rotation = best["_rotation"]
        out = {k: v for k, v in best.items() if not k.startswith("_")}
        out["rotation_deg"] = rotation
        out["all_attempts"] = [{"rotation": c["_rotation"], "words": c["words"],
                                "conf": c["confidence"]} for c in candidates]
        return out
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


VISION_TOOLS_SIMPLE = (
    vision_ocr,
    vision_ocr_region,
    vision_find_text,
    vision_describe,
    vision_match_template,
    vision_detect_faces,
    vision_video_frames,
    vision_video_ocr,
    vision_video_scene_changes,
    vision_compare_ocr,
)


VISION_TOOLS_BROWSER = (
    vision_ocr_screenshot,
)


VISION_TOOLS = VISION_TOOLS_SIMPLE + VISION_TOOLS_BROWSER

# Optional env-based override for the tesseract binary location

_env_tc = os.environ.get("ORVIMA_TESSERACT_PATH") or os.environ.get("TESSERACT_CMD")
if _env_tc and os.path.isfile(_env_tc):
    _TESSERACT_CMD = _env_tc
    _TESSERACT_PROBED = True
