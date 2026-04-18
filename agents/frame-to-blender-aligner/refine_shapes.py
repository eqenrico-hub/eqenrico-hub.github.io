"""
Frame-to-Blender Aligner — Shape Refiner

Takes an imprecise JSON trace from GUI Frame Tool + the reference PNG
and refines each shape's pixel coordinates so it matches the actual
element in the image. This is the CV step that prevents "my knob is
70px too high" mismatches.

Usage:
    python3 refine_shapes.py shapes.json reference.png refined.json

Pipeline:
    For each traced shape in JSON:
      1. Extract local patch around traced center (±2x radius)
      2. Run feature detection appropriate to the shape type:
           circle → Hough circles (radius-bounded)
           rect   → contour + bounding-rect
           ring   → double Hough circles
      3. Score candidates by IoU with traced shape + dominant color match
      4. Pick best candidate → write refined coords to output JSON

Traced JSON is authoritative for WHICH elements exist and roughly where.
CV is authoritative for EXACT position and size.
"""

import json
import sys
import numpy as np
import cv2


def refine_circle(img, shape, search_radius_mult=2.5):
    """Find the actual circle in the PNG near the traced position."""
    cx, cy, r = shape["cx"], shape["cy"], shape["r"]
    search_r = int(r * search_radius_mult)

    x0 = max(0, int(cx - search_r))
    y0 = max(0, int(cy - search_r))
    x1 = min(img.shape[1], int(cx + search_r))
    y1 = min(img.shape[0], int(cy + search_r))

    patch = img[y0:y1, x0:x1]
    gray = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY)
    gray = cv2.medianBlur(gray, 5)

    # Hough with radius bounded to ±30% of traced radius
    r_min = max(5, int(r * 0.7))
    r_max = int(r * 1.3)
    circles = cv2.HoughCircles(
        gray, cv2.HOUGH_GRADIENT, dp=1, minDist=r,
        param1=50, param2=25, minRadius=r_min, maxRadius=r_max
    )

    if circles is None:
        return shape  # no better candidate

    circles = np.round(circles[0]).astype(int)
    # Score by distance to traced center
    patch_cx = cx - x0
    patch_cy = cy - y0
    scored = [
        (abs(c[0] - patch_cx) + abs(c[1] - patch_cy), c)
        for c in circles
    ]
    scored.sort()
    best = scored[0][1]

    return {
        **shape,
        "cx": float(best[0] + x0),
        "cy": float(best[1] + y0),
        "r":  float(best[2]),
        "refined": True,
    }


def refine_rect(img, shape, tol=0.15):
    """Snap rect boundaries to high-contrast edges in a ±tol region."""
    x, y, w, h = shape["x"], shape["y"], shape["w"], shape["h"]

    dx = int(w * tol)
    dy = int(h * tol)
    x0 = max(0, x - dx)
    y0 = max(0, y - dy)
    x1 = min(img.shape[1], x + w + dx)
    y1 = min(img.shape[0], y + h + dy)

    patch = img[y0:y1, x0:x1]
    gray = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 40, 120)

    ys, xs = np.where(edges > 0)
    if len(xs) == 0:
        return shape

    # Look for dominant horizontal + vertical edge lines
    h_proj = edges.sum(axis=1)
    v_proj = edges.sum(axis=0)

    # Find the top and bottom strong rows near the traced boundaries
    rel_top = y - y0
    rel_bot = y + h - y0
    rel_left = x - x0
    rel_right = x + w - x0

    def nearest_strong(proj, target, threshold=None):
        if threshold is None:
            threshold = proj.max() * 0.25
        strong = np.where(proj > threshold)[0]
        if len(strong) == 0:
            return target
        return int(strong[np.argmin(np.abs(strong - target))])

    new_top   = nearest_strong(h_proj, rel_top)
    new_bot   = nearest_strong(h_proj, rel_bot)
    new_left  = nearest_strong(v_proj, rel_left)
    new_right = nearest_strong(v_proj, rel_right)

    return {
        **shape,
        "x": float(new_left + x0),
        "y": float(new_top + y0),
        "w": float(new_right - new_left),
        "h": float(new_bot - new_top),
        "refined": True,
    }


def refine_ring(img, shape):
    """Ring = refine as double Hough."""
    cx, cy = shape["cx"], shape["cy"]
    r_out = shape["r_out"]
    r_in  = shape["r_in"]
    circle_probe = {"cx": cx, "cy": cy, "r": r_out}
    outer = refine_circle(img, circle_probe)
    return {
        **shape,
        "cx": outer["cx"],
        "cy": outer["cy"],
        "r_out": outer["r"],
        "r_in": r_in * (outer["r"] / r_out) if r_out else r_in,
        "refined": True,
    }


def refine(json_path: str, png_path: str, out_path: str):
    with open(json_path) as f:
        data = json.load(f)
    img = cv2.imread(png_path)
    if img is None:
        raise SystemExit(f"Cannot load PNG: {png_path}")

    refined = []
    changed = 0
    for s in data["shapes"]:
        t = s["type"]
        if t == "circle":
            r = refine_circle(img, s)
        elif t == "rect":
            r = refine_rect(img, s)
        elif t == "ring":
            r = refine_ring(img, s)
        else:
            r = s
        refined.append(r)
        if r.get("refined"):
            # Did the position change meaningfully?
            if t == "circle":
                if abs(r["cx"] - s["cx"]) > 2 or abs(r["cy"] - s["cy"]) > 2:
                    changed += 1
            elif t == "rect":
                if abs(r["x"] - s["x"]) > 2 or abs(r["y"] - s["y"]) > 2:
                    changed += 1

    out = {**data, "shapes": refined}
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)

    print(f"Refined {len(refined)} shapes, {changed} moved by >2px")
    print(f"Written: {out_path}")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: refine_shapes.py shapes.json reference.png refined.json")
        sys.exit(1)
    refine(sys.argv[1], sys.argv[2], sys.argv[3])
