"""
Image-to-Blender element detection (v3 — full coverage).

v3 goals: detect everything on a GUI PNG so a 3D rebuild needs no chassis image.

Stages:
  1. Multi-band Hough circles (tiny/medium/large) with dedupe — knobs, buttons, LEDs
  2. Color-region segmentation — finds distinct UI color blobs (pink buttons, amber
     LEDs, teal chassis slabs, etc.) regardless of shape
  3. Rectangular UI region detection via adaptive threshold + connected components
  4. Text detection via Tesseract OCR — labels, titles, parameter values
  5. Vertical-bar strip detection — for spectrum visualizers
  6. Keyboard strip detection
  7. Color-sampling: every detected element gets a dominant color from the PNG so
     the Blender rebuild can match the original palette per-element

Usage:
    python3 detect.py <gui_image.png> [--out spec.json] [--ocr]
"""
import cv2
import numpy as np
import json
import sys
from pathlib import Path

try:
    import pytesseract
    HAS_OCR = True
except ImportError:
    HAS_OCR = False


# ============================================================
# Helpers
# ============================================================
def _dominant_color(img, x, y, w, h):
    """Get median BGR of the region."""
    roi = img[max(0, y):y+h, max(0, x):x+w]
    if roi.size == 0:
        return (0, 0, 0)
    # Median is robust to highlights/shadows
    med = np.median(roi.reshape(-1, 3), axis=0)
    return tuple(int(c) for c in med)


def _bgr_to_rgba01(bgr):
    return (bgr[2] / 255.0, bgr[1] / 255.0, bgr[0] / 255.0, 1.0)


# ============================================================
# Circle detection (unchanged from v2)
# ============================================================
def _hough_circles(gray, min_r, max_r, min_dist, param2):
    blur = cv2.medianBlur(gray, 7)
    c = cv2.HoughCircles(
        blur, cv2.HOUGH_GRADIENT, dp=1, minDist=min_dist,
        param1=100, param2=param2, minRadius=min_r, maxRadius=max_r,
    )
    if c is None:
        return []
    return [(int(x), int(y), int(r)) for x, y, r in np.round(c[0]).astype(int)]


def _dedupe_circles(circles, dist_threshold=0.6):
    by_r = sorted(circles, key=lambda c: -c[2])
    keep = []
    for cx, cy, r in by_r:
        if not any(((cx - kx) ** 2 + (cy - ky) ** 2) ** 0.5 < dist_threshold * max(r, kr)
                   for kx, ky, kr in keep):
            keep.append((cx, cy, r))
    keep.sort(key=lambda c: (c[1], c[0]))
    return keep


# ============================================================
# Rectangular region detection via solid-region segmentation
# ============================================================
def detect_rectangular_regions(img, exclude_circles, exclude_margin=12):
    H, W = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    th = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV,
        blockSize=51, C=4,
    )
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    cleaned = cv2.morphologyEx(th, cv2.MORPH_OPEN, kernel)
    num, labels, stats, _ = cv2.connectedComponentsWithStats(cleaned, connectivity=8)

    def near_circle(cx, cy):
        for kx, ky, kr in exclude_circles:
            if abs(cx - kx) < kr + exclude_margin and abs(cy - ky) < kr + exclude_margin:
                return True
        return False

    rects = []
    for i in range(1, num):
        x, y, w, h, area = stats[i]
        if area < 400 or area > W * H * 0.3:
            continue
        aspect = w / h if h else 0
        solidity = area / (w * h) if (w * h) else 0
        if solidity < 0.45:
            continue
        cx, cy = x + w // 2, y + h // 2
        if near_circle(cx, cy):
            continue
        # Classify
        if 0.15 < aspect < 0.5 and h > 80 and w < 80:
            kind = "vertical_slider"
        elif 2.0 < aspect < 8.0 and 18 < h < 55:
            kind = "pill_button"
        elif 0.6 < aspect < 1.6 and 25 < h < 90:
            kind = "square_button"
        elif 3.0 < aspect < 15.0 and 15 < h < 40:
            kind = "label_or_dropdown"
        elif 0.5 < aspect < 2.0 and h > 80:
            kind = "panel"
        else:
            continue
        color = _dominant_color(img, x, y, w, h)
        rects.append({
            "x": int(x), "y": int(y), "w": int(w), "h": int(h),
            "kind": kind, "bgr": list(color), "rgba": _bgr_to_rgba01(color),
        })
    return rects


# ============================================================
# Color-region segmentation — catches buttons/LEDs of distinctive hue
# ============================================================
def detect_color_regions(img, exclude_circles, exclude_rects):
    """
    Look for saturated non-chassis color blobs (pink/red buttons, amber LEDs, etc.).
    Uses HSV saturation + value thresholds.
    """
    H, W = img.shape[:2]
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    s = hsv[:, :, 1]
    v = hsv[:, :, 2]
    # High saturation + medium value = accent UI elements
    mask = ((s > 120) & (v > 90) & (v < 250)).astype(np.uint8) * 255
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    num, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)

    def near_circle(cx, cy):
        return any(abs(cx - kx) < kr + 15 and abs(cy - ky) < kr + 15
                   for kx, ky, kr in exclude_circles)

    def inside_rect(cx, cy):
        return any(r["x"] < cx < r["x"] + r["w"] and r["y"] < cy < r["y"] + r["h"]
                   for r in exclude_rects)

    regions = []
    for i in range(1, num):
        x, y, w, h, area = stats[i]
        if area < 150 or area > W * H * 0.1:
            continue
        cx, cy = x + w // 2, y + h // 2
        if near_circle(cx, cy):
            continue
        color = _dominant_color(img, x, y, w, h)
        regions.append({
            "x": int(x), "y": int(y), "w": int(w), "h": int(h),
            "bgr": list(color), "rgba": _bgr_to_rgba01(color),
        })
    return regions


# ============================================================
# Vertical-bar strip (spectrum visualizer)
# ============================================================
def detect_spectrum_strip(img):
    """Find a horizontal band full of tall narrow vertical colored bars."""
    H, W = img.shape[:2]
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    s = hsv[:, :, 1]
    # High saturation regions (spectrum bars are typically purple/pink/blue)
    mask = (s > 90).astype(np.uint8) * 255
    # Vertical kernel collapses each column
    col_sum = np.sum(mask, axis=0)
    # Rows: find a strip with highest concentration of saturated pixels
    row_sum = np.sum(mask, axis=1)
    # Top row and bottom row of spectrum: rolling window
    strip_rows = []
    for y in range(0, H - 50, 20):
        if row_sum[y:y+50].sum() > W * 50 * 0.15:
            strip_rows.append(y)
    if not strip_rows:
        return None
    y1 = min(strip_rows)
    y2 = max(strip_rows) + 50
    # Limit horizontal range to where most saturated cols are
    thresh = np.max(col_sum) * 0.2
    xs = np.where(col_sum > thresh)[0]
    if len(xs) < 50:
        return None
    x1, x2 = int(xs.min()), int(xs.max())
    if x2 - x1 < W * 0.2 or y2 - y1 < 40:
        return None
    return {"x1": x1, "y1": int(y1), "x2": x2, "y2": int(y2)}


def detect_keyboard_strip(gray):
    H, W = gray.shape
    bottom = gray[int(H * 0.75):, :]
    _, kb_mask = cv2.threshold(bottom, 170, 255, cv2.THRESH_BINARY)
    ys, xs = np.where(kb_mask > 0)
    if len(xs) < 500:
        return None
    kb_x1, kb_x2 = int(xs.min()), int(xs.max())
    kb_y1 = int(ys.min()) + int(H * 0.75)
    kb_y2 = int(ys.max()) + int(H * 0.75)
    if kb_x2 - kb_x1 < W * 0.4 or kb_y2 - kb_y1 < 30:
        return None
    return {"x1": kb_x1, "y1": kb_y1, "x2": kb_x2, "y2": kb_y2}


# ============================================================
# OCR for text labels
# ============================================================
def detect_text(img_path):
    if not HAS_OCR:
        return []
    try:
        data = pytesseract.image_to_data(
            img_path, output_type=pytesseract.Output.DICT,
            config="--psm 11 --oem 1",  # sparse text
        )
    except Exception as e:
        print(f"OCR failed: {e}")
        return []
    texts = []
    for i in range(len(data["text"])):
        txt = (data["text"][i] or "").strip()
        conf = int(data["conf"][i]) if data["conf"][i] != "-1" else -1
        if len(txt) < 1 or conf < 40:
            continue
        texts.append({
            "text": txt,
            "x": int(data["left"][i]), "y": int(data["top"][i]),
            "w": int(data["width"][i]), "h": int(data["height"][i]),
            "confidence": conf,
        })
    return texts


# ============================================================
# Main
# ============================================================
def detect(img_path, debug_out=None, run_ocr=False):
    img = cv2.imread(img_path)
    if img is None:
        raise SystemExit(f"Cannot read {img_path}")
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    H, W = gray.shape

    # Circles, multi-band
    large = _hough_circles(gray, 55, 130, 100, 55)
    medium = _hough_circles(gray, 22, 55, 60, 45)
    tiny = _hough_circles(gray, 8, 22, 30, 25)

    def in_zone(c):
        return 50 < c[1] < H - 50
    merged = _dedupe_circles([c for c in large + medium if in_zone(c)], 0.7)
    small = [c for c in tiny if not any(
        ((c[0] - kx) ** 2 + (c[1] - ky) ** 2) ** 0.5 < kr + 5 for kx, ky, kr in merged)]

    # Sample colors for circles
    knobs_with_color = []
    for cx, cy, r in merged:
        color = _dominant_color(img, max(0, cx - r), max(0, cy - r), 2 * r, 2 * r)
        knobs_with_color.append({"cx": cx, "cy": cy, "r": r,
                                 "bgr": list(color), "rgba": _bgr_to_rgba01(color)})
    small_with_color = []
    for cx, cy, r in small:
        color = _dominant_color(img, max(0, cx - r), max(0, cy - r), 2 * r, 2 * r)
        small_with_color.append({"cx": cx, "cy": cy, "r": r,
                                 "bgr": list(color), "rgba": _bgr_to_rgba01(color)})

    # Rectangles
    rects = detect_rectangular_regions(img, merged)

    # Color-distinct UI blobs
    color_regions = detect_color_regions(img, merged, rects)

    # Spectrum strip
    spectrum = detect_spectrum_strip(img)

    # Keyboard
    keyboard = detect_keyboard_strip(gray)

    # OCR
    texts = detect_text(img_path) if run_ocr else []

    result = {
        "image": img_path, "width": W, "height": H,
        "knobs": knobs_with_color,
        "small_circles": small_with_color,
        "rectangles": rects,
        "color_regions": color_regions,
        "spectrum_strip": spectrum,
        "keyboard_strip": keyboard,
        "texts": texts,
    }

    if debug_out:
        vis = img.copy()
        for i, k in enumerate(result["knobs"]):
            cv2.circle(vis, (k["cx"], k["cy"]), k["r"], (0, 255, 255), 3)
        for s in result["small_circles"]:
            cv2.circle(vis, (s["cx"], s["cy"]), s["r"], (255, 180, 80), 2)
        for r in result["rectangles"]:
            cv2.rectangle(vis, (r["x"], r["y"]), (r["x"] + r["w"], r["y"] + r["h"]), (80, 255, 80), 2)
        for r in result["color_regions"]:
            cv2.rectangle(vis, (r["x"], r["y"]), (r["x"] + r["w"], r["y"] + r["h"]), (255, 80, 255), 2)
        if result["spectrum_strip"]:
            s = result["spectrum_strip"]
            cv2.rectangle(vis, (s["x1"], s["y1"]), (s["x2"], s["y2"]), (200, 100, 255), 4)
        if result["keyboard_strip"]:
            kb = result["keyboard_strip"]
            cv2.rectangle(vis, (kb["x1"], kb["y1"]), (kb["x2"], kb["y2"]), (255, 255, 255), 3)
        for t in result["texts"]:
            cv2.rectangle(vis, (t["x"], t["y"]), (t["x"] + t["w"], t["y"] + t["h"]), (0, 180, 255), 1)
        cv2.imwrite(debug_out, vis)
    return result


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 detect.py <gui_image.png> [--out spec.json] [--ocr]")
        sys.exit(1)
    img_path = sys.argv[1]
    out_json = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else str(
        Path(img_path).with_suffix(".detected.json"))
    debug_png = str(Path(img_path).with_suffix(".detected.png"))
    run_ocr = "--ocr" in sys.argv
    spec = detect(img_path, debug_out=debug_png, run_ocr=run_ocr)
    with open(out_json, "w") as f:
        json.dump(spec, f, indent=2)
    print(f"Wrote {out_json}")
    print(f"Debug: {debug_png}")
    print(f"Found: knobs={len(spec['knobs'])}, small={len(spec['small_circles'])}, "
          f"rects={len(spec['rectangles'])}, color_regions={len(spec['color_regions'])}, "
          f"spectrum={'yes' if spec['spectrum_strip'] else 'no'}, "
          f"keyboard={'yes' if spec['keyboard_strip'] else 'no'}, "
          f"texts={len(spec['texts'])}")
