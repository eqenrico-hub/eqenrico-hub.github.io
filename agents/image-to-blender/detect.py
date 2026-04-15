"""
Image-to-Blender element detection.

Takes a VST GUI PNG (typically output from the VST GUI pipeline prompt A,
or a real plugin screenshot) and extracts interactive element positions
by layered computer-vision analysis:

  1. Hough circles (knobs, buttons, EQ nodes) at multiple radius bands
  2. Contour extraction (slider thumbs, rectangular buttons, piano keys)
  3. Color clustering + region grouping (piano key bed, chassis regions)

Output: a single JSON spec consumed by apply.py in Blender.

Usage:
    python3 detect.py <gui_image.png> [--out path/to/spec.json]
"""
import cv2
import numpy as np
import json
import sys
from pathlib import Path

def detect(img_path: str, debug_out: str | None = None):
    img = cv2.imread(img_path)
    if img is None:
        raise SystemExit(f"Cannot read {img_path}")
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    H, W = gray.shape
    result = {
        "image": img_path,
        "width": W, "height": H,
        "knobs": [],
        "small_circles": [],   # EQ nodes, tiny buttons
        "rectangles": [],      # sliders, buttons, piano keys
        "keyboard_strip": None,
    }

    # --- STAGE 1: Knobs (medium circles, 22-55px radius) ---
    blur = cv2.medianBlur(gray, 7)
    knob_circles = cv2.HoughCircles(
        blur, cv2.HOUGH_GRADIENT, dp=1, minDist=60,
        param1=100, param2=45, minRadius=22, maxRadius=55,
    )
    if knob_circles is not None:
        for c in np.round(knob_circles[0]).astype(int):
            cx, cy, r = int(c[0]), int(c[1]), int(c[2])
            # Filter out header/footer decorative regions
            if 70 < cy < 810:
                result["knobs"].append({"cx": cx, "cy": cy, "r": r})

    # --- STAGE 2: Small circles (EQ nodes, tiny buttons), 8-22px ---
    small = cv2.HoughCircles(
        blur, cv2.HOUGH_GRADIENT, dp=1, minDist=30,
        param1=80, param2=25, minRadius=8, maxRadius=22,
    )
    if small is not None:
        seen_knobs = {(k["cx"], k["cy"]) for k in result["knobs"]}
        for c in np.round(small[0]).astype(int):
            cx, cy, r = int(c[0]), int(c[1]), int(c[2])
            # Exclude if near a larger detected knob (likely the inner cap)
            if any(abs(cx - kx) < 40 and abs(cy - ky) < 40 for (kx, ky) in seen_knobs):
                continue
            result["small_circles"].append({"cx": cx, "cy": cy, "r": r})

    # --- STAGE 3: Rectangular elements (contours) ---
    # Threshold first so we only pick up well-defined boundaries
    edges = cv2.Canny(blur, 60, 140)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        area = w * h
        if area < 400 or area > (W * H) * 0.2:
            continue
        aspect = w / h if h else 0
        # Skip if near/inside a detected knob
        near_knob = any(
            abs((x + w/2) - k["cx"]) < k["r"] and abs((y + h/2) - k["cy"]) < k["r"]
            for k in result["knobs"]
        )
        if near_knob:
            continue
        # Classify by rough shape
        kind = None
        if 0.15 < aspect < 0.5 and 60 < h < 350:
            kind = "vertical_slider_candidate"
        elif 2.0 < aspect < 6.0 and 15 < h < 60:
            kind = "horizontal_button_candidate"
        elif 0.6 < aspect < 1.4 and 20 < h < 80:
            kind = "square_button_candidate"
        if kind:
            result["rectangles"].append({
                "x": int(x), "y": int(y), "w": int(w), "h": int(h),
                "kind": kind,
            })

    # --- STAGE 4: Keyboard strip (horizontal pale zone at bottom) ---
    # Look in bottom ~30% of the image for a wide region of bright pixels
    bottom = gray[int(H * 0.75):, :]
    _, kb_mask = cv2.threshold(bottom, 170, 255, cv2.THRESH_BINARY)
    ys, xs = np.where(kb_mask > 0)
    if len(xs) > 500:
        kb_x1, kb_x2 = int(xs.min()), int(xs.max())
        kb_y1 = int(ys.min()) + int(H * 0.75)
        kb_y2 = int(ys.max()) + int(H * 0.75)
        if kb_x2 - kb_x1 > W * 0.4 and kb_y2 - kb_y1 > 30:
            result["keyboard_strip"] = {
                "x1": kb_x1, "y1": kb_y1, "x2": kb_x2, "y2": kb_y2,
            }

    # --- DEBUG OUTPUT ---
    if debug_out:
        vis = img.copy()
        for k in result["knobs"]:
            cv2.circle(vis, (k["cx"], k["cy"]), k["r"], (0, 255, 255), 3)
        for s in result["small_circles"]:
            cv2.circle(vis, (s["cx"], s["cy"]), s["r"], (255, 180, 80), 2)
        for r in result["rectangles"]:
            color = {"vertical_slider_candidate": (80, 255, 80),
                     "horizontal_button_candidate": (80, 80, 255),
                     "square_button_candidate": (255, 80, 255)}[r["kind"]]
            cv2.rectangle(vis, (r["x"], r["y"]), (r["x"] + r["w"], r["y"] + r["h"]), color, 2)
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
    out_json = None
    if "--out" in sys.argv:
        out_json = sys.argv[sys.argv.index("--out") + 1]
    else:
        out_json = str(Path(img_path).with_suffix(".detected.json"))
    debug_png = str(Path(img_path).with_suffix(".detected.png"))
    spec = detect(img_path, debug_out=debug_png)
    with open(out_json, "w") as f:
        json.dump(spec, f, indent=2)
    print(f"Wrote {out_json}")
    print(f"Debug: {debug_png}")
    print(f"Found: {len(spec['knobs'])} knobs, {len(spec['small_circles'])} small circles, "
          f"{len(spec['rectangles'])} rects, keyboard={'yes' if spec['keyboard_strip'] else 'no'}")
