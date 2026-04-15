"""
Stage 2 refinement: snap authoritative positions to OpenCV detections,
sample dominant colors from the chassis PNG, and write an updated spec.

Usage:
    python3 refine.py <spec.json> <chassis.png> [--out refined.json]
"""
import sys, json, argparse
import numpy as np
import cv2
from detect import detect as cv_detect


def _median_color_in_bbox(img, x, y, w, h, inset=0.35):
    """Sample median of the INNER core of the bounding box to avoid chassis bleed."""
    x = max(0, int(x)); y = max(0, int(y))
    w = int(w); h = int(h)
    # Shrink by `inset` on each side
    dx = int(w * inset); dy = int(h * inset)
    x1 = x + dx; y1 = y + dy
    x2 = min(img.shape[1], x + w - dx)
    y2 = min(img.shape[0], y + h - dy)
    if x2 <= x1 or y2 <= y1:
        # Fallback: single center pixel
        cx = max(0, min(img.shape[1] - 1, x + w // 2))
        cy = max(0, min(img.shape[0] - 1, y + h // 2))
        return tuple(int(c) for c in img[cy, cx])
    roi = img[y1:y2, x1:x2]
    med = np.median(roi.reshape(-1, 3), axis=0)
    return tuple(int(c) for c in med)


def _median_color_circle(img, cx, cy, r):
    # Sample the inner 60% of the circle
    inner = max(3, int(r * 0.6))
    return _median_color_in_bbox(img, cx - inner, cy - inner, 2 * inner, 2 * inner, inset=0.0)


def _bgr_to_rgba01(bgr):
    return (bgr[2] / 255.0, bgr[1] / 255.0, bgr[0] / 255.0, 1.0)


def _snap_circle(cx, cy, expected_r, cv_circles, tolerance=120):
    """Find the closest CV-detected circle within tolerance whose radius is plausible."""
    best = None; best_d = tolerance
    for dcx, dcy, dr in cv_circles:
        d = ((cx - dcx) ** 2 + (cy - dcy) ** 2) ** 0.5
        # Accept radii within 80% of expected to catch varied knob styles
        if d < best_d and abs(dr - expected_r) < max(expected_r * 0.8, 20):
            best_d = d
            best = (dcx, dcy, dr)
    return best


def refine(spec_path, chassis_path, out_path):
    spec = json.load(open(spec_path))
    img = cv2.imread(chassis_path)
    if img is None:
        raise SystemExit(f"Cannot read {chassis_path}")

    # Run detect on the chassis to get CV circles for snapping
    cv_spec = cv_detect(chassis_path, debug_out=None, run_ocr=False)
    cv_circles = [(k["cx"], k["cy"], k["r"]) for k in cv_spec["knobs"]] + \
                 [(s["cx"], s["cy"], s["r"]) for s in cv_spec["small_circles"]]

    # --- Snap + sample knobs ---
    for k in spec.get("knobs", []):
        snap = _snap_circle(k["cx"], k["cy"], k.get("r", 30), cv_circles, tolerance=60)
        if snap:
            k["cx"], k["cy"], k["r"] = snap
        color = _median_color_circle(img, k["cx"], k["cy"], k["r"])
        k["bgr"] = list(color)
        k["rgba"] = _bgr_to_rgba01(color)

    for s in spec.get("small_circles", []):
        snap = _snap_circle(s["cx"], s["cy"], s.get("r", 16), cv_circles, tolerance=40)
        if snap:
            s["cx"], s["cy"], s["r"] = snap
        color = _median_color_circle(img, s["cx"], s["cy"], s["r"])
        s["bgr"] = list(color)
        s["rgba"] = _bgr_to_rgba01(color)

    # --- Sample rectangle colors (no snap — authoritative positions trusted) ---
    for r in spec.get("rectangles", []):
        color = _median_color_in_bbox(img, r["x"], r["y"], r["w"], r["h"])
        r["bgr"] = list(color)
        r["rgba"] = _bgr_to_rgba01(color)

    # --- Text: sample color from bounding box ---
    for t in spec.get("texts", []):
        color = _median_color_in_bbox(img, t["x"], t["y"], t["w"], t["h"])
        t["bgr"] = list(color)
        t["rgba"] = _bgr_to_rgba01(color)

    with open(out_path, "w") as f:
        json.dump(spec, f, indent=2)
    print(f"Wrote refined spec: {out_path}")
    print(f"  Sampled colors for {len(spec['knobs'])} knobs, "
          f"{len(spec['small_circles'])} small, {len(spec['rectangles'])} rects, "
          f"{len(spec['texts'])} texts")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("spec")
    p.add_argument("chassis")
    p.add_argument("--out", default=None)
    args = p.parse_args()
    out = args.out or args.spec.replace(".json", ".refined.json")
    refine(args.spec, args.chassis, out)
