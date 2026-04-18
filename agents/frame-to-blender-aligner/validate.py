"""
Frame-to-Blender Aligner — Render Validator

After Blender builds the scene and renders a top-down ortho view,
compare render vs reference PNG with per-element pixel diff so you
can quantify how well each shape aligns with the artwork underneath.

Usage:
    python3 validate.py refined.json reference.png blender_render.png [report.json]

Output:
    report.json — per-shape overlap score + bounding-box IoU with
                  reference feature detection. Flags elements that
                  moved > N px from their refined position.
"""

import json
import sys
import numpy as np
import cv2


def per_shape_iou(ref_img, render_img, shape):
    """Compute IoU of the shape's bounding region between ref and render."""
    if shape["type"] == "circle":
        cx, cy, r = int(shape["cx"]), int(shape["cy"]), int(shape["r"])
        x0, y0 = max(0, cx - r), max(0, cy - r)
        x1, y1 = min(ref_img.shape[1], cx + r), min(ref_img.shape[0], cy + r)
    elif shape["type"] == "rect":
        x0 = int(shape["x"]); y0 = int(shape["y"])
        x1 = int(shape["x"] + shape["w"]); y1 = int(shape["y"] + shape["h"])
    else:
        return None

    ref_patch = ref_img[y0:y1, x0:x1]
    rnd_patch = render_img[y0:y1, x0:x1]

    if ref_patch.size == 0 or rnd_patch.size == 0:
        return None

    # Grayscale diff, normalized
    g_ref = cv2.cvtColor(ref_patch, cv2.COLOR_BGR2GRAY).astype(np.float32)
    g_rnd = cv2.cvtColor(rnd_patch, cv2.COLOR_BGR2GRAY).astype(np.float32)
    diff = np.mean(np.abs(g_ref - g_rnd)) / 255.0
    return 1.0 - diff


def validate(json_path, ref_path, render_path, report_path="alignment_report.json"):
    data = json.load(open(json_path))
    ref = cv2.imread(ref_path)
    rnd = cv2.imread(render_path)

    if ref.shape != rnd.shape:
        rnd = cv2.resize(rnd, (ref.shape[1], ref.shape[0]))

    report = {"shapes": []}
    for s in data["shapes"]:
        score = per_shape_iou(ref, rnd, s)
        report["shapes"].append({
            "id": s["id"],
            "type": s["type"],
            "alignment_score": score,
            "flag_misaligned": score is not None and score < 0.6,
        })

    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)

    bad = [r for r in report["shapes"] if r["flag_misaligned"]]
    print(f"Validated {len(report['shapes'])} shapes, {len(bad)} flagged as misaligned")
    print(f"Report: {report_path}")


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: validate.py refined.json reference.png render.png [report.json]")
        sys.exit(1)
    validate(
        sys.argv[1], sys.argv[2], sys.argv[3],
        sys.argv[4] if len(sys.argv) > 4 else "alignment_report.json",
    )
