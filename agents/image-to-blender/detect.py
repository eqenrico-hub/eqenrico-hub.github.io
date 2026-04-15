"""
Image-to-Blender element detection (v2).

Improvements over v1:
  - Knobs: 3 radius bands (tiny 8-22, medium 22-55, large 55-130) — catches hero knobs
  - Knob deduplication: merges overlapping detections across radius bands
  - Rectangles: SOLID-REGION detection via adaptive threshold + connected components,
    not edge-based Canny (which produced 70+ false positives from chassis texture)
  - Color-based classification of rectangles (bright = slider thumb, dark = button/panel)

Usage:
    python3 detect.py <gui_image.png> [--out path/to/spec.json]
"""
import cv2
import numpy as np
import json
import sys
from pathlib import Path


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
    """Merge overlapping circles (prefer larger r). Returns sorted top-to-bottom."""
    by_r = sorted(circles, key=lambda c: -c[2])
    keep = []
    for cx, cy, r in by_r:
        overlap = False
        for kx, ky, kr in keep:
            d = ((cx - kx) ** 2 + (cy - ky) ** 2) ** 0.5
            if d < dist_threshold * max(r, kr):
                overlap = True
                break
        if not overlap:
            keep.append((cx, cy, r))
    keep.sort(key=lambda c: (c[1], c[0]))
    return keep


def detect_rectangular_regions(img, exclude_circles, exclude_margin=30):
    """
    Find rectangular UI elements by solid-color region segmentation.
    Uses mean-shift-like quantization to group similar-color neighborhoods,
    then picks regions whose bounding boxes are rectangle-like.
    """
    H, W = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Adaptive threshold pulls out solid UI elements vs textured chassis
    th = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV,
        blockSize=51, C=4,
    )
    # Morphological opening kills texture noise
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    cleaned = cv2.morphologyEx(th, cv2.MORPH_OPEN, kernel)

    # Connected components
    num, labels, stats, _ = cv2.connectedComponentsWithStats(cleaned, connectivity=8)

    def near_circle(cx, cy):
        for kx, ky, kr in exclude_circles:
            if abs(cx - kx) < kr + exclude_margin and abs(cy - ky) < kr + exclude_margin:
                return True
        return False

    rects = []
    for i in range(1, num):
        x, y, w, h, area = stats[i]
        if area < 600:
            continue
        if area > W * H * 0.3:
            continue
        aspect = w / h if h else 0
        solidity = area / (w * h) if (w * h) else 0
        if solidity < 0.55:
            continue
        cx, cy = x + w // 2, y + h // 2
        if near_circle(cx, cy):
            continue
        # Classify by shape
        kind = None
        if 0.15 < aspect < 0.5 and h > 80 and w < 80:
            kind = "vertical_slider_candidate"
        elif 2.0 < aspect < 7.0 and 18 < h < 55:
            kind = "horizontal_button_candidate"
        elif 0.6 < aspect < 1.6 and 25 < h < 90:
            kind = "square_button_candidate"
        if kind is None:
            continue
        # Sample mean brightness in the region → used later to distinguish bright thumb vs dark button
        roi = gray[y:y+h, x:x+w]
        brightness = float(roi.mean())
        rects.append({
            "x": int(x), "y": int(y), "w": int(w), "h": int(h),
            "kind": kind, "brightness": round(brightness, 1),
        })
    return rects


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


def detect(img_path, debug_out=None):
    img = cv2.imread(img_path)
    if img is None:
        raise SystemExit(f"Cannot read {img_path}")
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    H, W = gray.shape

    # === Multi-band circle detection + dedupe ===
    large = _hough_circles(gray, 55, 130, min_dist=100, param2=55)
    medium = _hough_circles(gray, 22, 55, min_dist=60, param2=45)
    tiny = _hough_circles(gray, 8, 22, min_dist=30, param2=25)

    # Exclude top/bottom strips from knob zone
    def in_knob_zone(c):
        return 70 < c[1] < 810

    large_f = [c for c in large if in_knob_zone(c)]
    medium_f = [c for c in medium if in_knob_zone(c)]

    # Merge large + medium, dedupe
    merged_knobs = _dedupe_circles(large_f + medium_f, dist_threshold=0.7)

    # Small circles: only keep ones not inside a detected knob
    def inside_any_knob(tx, ty, tr):
        for kx, ky, kr in merged_knobs:
            if ((tx - kx) ** 2 + (ty - ky) ** 2) ** 0.5 < kr + 5:
                return True
        return False

    small_circles = [c for c in tiny if not inside_any_knob(*c)]
    # Further filter: keep only small circles that look like EQ nodes or standalone tiny buttons
    # (y range 600-800, reasonable small radius)
    small_circles = [c for c in small_circles if 640 < c[1] < 800 and 8 <= c[2] <= 20]

    # === Rectangle detection (solid-region based) ===
    rectangles = detect_rectangular_regions(img, exclude_circles=merged_knobs)
    # Further filter obviously-spurious text fragments
    rectangles = [r for r in rectangles if r["w"] * r["h"] >= 1500]

    # === Keyboard strip ===
    keyboard = detect_keyboard_strip(gray)

    result = {
        "image": img_path, "width": W, "height": H,
        "knobs": [{"cx": c[0], "cy": c[1], "r": c[2]} for c in merged_knobs],
        "small_circles": [{"cx": c[0], "cy": c[1], "r": c[2]} for c in small_circles],
        "rectangles": rectangles,
        "keyboard_strip": keyboard,
    }

    # === Debug overlay ===
    if debug_out:
        vis = img.copy()
        for i, k in enumerate(result["knobs"]):
            cv2.circle(vis, (k["cx"], k["cy"]), k["r"], (0, 255, 255), 3)
            cv2.putText(vis, f"K{i}", (k["cx"] + k["r"] + 3, k["cy"] + 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        for i, s in enumerate(result["small_circles"]):
            cv2.circle(vis, (s["cx"], s["cy"]), s["r"], (255, 180, 80), 2)
            cv2.putText(vis, f"N{i}", (s["cx"] + s["r"] + 3, s["cy"] + 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 180, 80), 1)
        kind_color = {
            "vertical_slider_candidate": (80, 255, 80),
            "horizontal_button_candidate": (80, 80, 255),
            "square_button_candidate": (255, 80, 255),
        }
        for i, r in enumerate(result["rectangles"]):
            c = kind_color[r["kind"]]
            cv2.rectangle(vis, (r["x"], r["y"]), (r["x"] + r["w"], r["y"] + r["h"]), c, 2)
            cv2.putText(vis, f"R{i}", (r["x"] + 4, r["y"] + 16),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, c, 1)
        if result["keyboard_strip"]:
            kb = result["keyboard_strip"]
            cv2.rectangle(vis, (kb["x1"], kb["y1"]), (kb["x2"], kb["y2"]), (255, 255, 255), 3)
        cv2.imwrite(debug_out, vis)

    return result


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 detect.py <gui_image.png> [--out spec.json]")
        sys.exit(1)
    img_path = sys.argv[1]
    out_json = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else str(
        Path(img_path).with_suffix(".detected.json"))
    debug_png = str(Path(img_path).with_suffix(".detected.png"))
    spec = detect(img_path, debug_out=debug_png)
    with open(out_json, "w") as f:
        json.dump(spec, f, indent=2)
    print(f"Wrote {out_json}")
    print(f"Debug: {debug_png}")
    print(f"Found: {len(spec['knobs'])} knobs, {len(spec['small_circles'])} small circles, "
          f"{len(spec['rectangles'])} rects, keyboard={'yes' if spec['keyboard_strip'] else 'no'}")
