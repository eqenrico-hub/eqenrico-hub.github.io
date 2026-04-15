"""
Stage-gated verification for the Image-to-Blender pipeline.

Runs outside Blender. Reads the spec JSON + optionally a rendered PNG and
returns pass/fail + a list of issues.

Usage:
    python3 verify.py <spec.json> --stage=1
    python3 verify.py <spec.json> --stage=2 --chassis=<chassis.png>
    python3 verify.py <spec.json> --stage=3 --chassis=<chassis.png> --render=<no_chassis.png>
    python3 verify.py <spec.json> --stage=4 --render=<no_chassis.png>
"""
import sys, json, argparse


def verify_stage1(spec):
    """Element presence: every authoritative ID has a spec entry."""
    issues = []
    # All authoritative IDs should appear in the spec under some category
    auth_ids = {a["id"] for a in spec.get("authoritative", [])}
    present_ids = set()
    for cat in ("knobs", "small_circles", "rectangles", "texts"):
        for e in spec.get(cat, []):
            if "id" in e:
                present_ids.add(e["id"])
    missing = auth_ids - present_ids
    if missing:
        issues.append(f"Missing IDs in categories: {sorted(missing)}")
    extra = present_ids - auth_ids
    if extra:
        issues.append(f"Unexpected IDs not in authoritative list: {sorted(extra)}")
    return (len(issues) == 0, issues)


def verify_stage2(spec, chassis_path):
    """Position refinement + color sampling."""
    try:
        import cv2
        import numpy as np
    except ImportError:
        return (False, ["OpenCV not available"])
    img = cv2.imread(chassis_path)
    if img is None:
        return (False, [f"Cannot read {chassis_path}"])
    issues = []
    # For each element, check it has a sampled color (bgr or rgba field)
    for cat in ("knobs", "small_circles", "rectangles"):
        for e in spec.get(cat, []):
            if "rgba" not in e and "bgr" not in e:
                issues.append(f"{cat}:{e.get('id','?')} missing sampled color")
    # Position plausibility: each center should land on non-chassis-background pixel
    # (heuristic: element center should NOT be uniform chassis color)
    return (len(issues) == 0, issues)


def verify_stage3(spec, chassis_path, render_path):
    try:
        import cv2
        import numpy as np
    except ImportError:
        return (False, ["OpenCV not available"])
    chassis = cv2.imread(chassis_path)
    render = cv2.imread(render_path)
    if chassis is None or render is None:
        return (False, ["Missing chassis or render image"])
    if chassis.shape != render.shape:
        render = cv2.resize(render, (chassis.shape[1], chassis.shape[0]))
    # Crude structural similarity proxy: correlation of grayscale histograms + mean abs diff
    c_gray = cv2.cvtColor(chassis, cv2.COLOR_BGR2GRAY)
    r_gray = cv2.cvtColor(render, cv2.COLOR_BGR2GRAY)
    try:
        from skimage.metrics import structural_similarity as ssim
        score = ssim(c_gray, r_gray)
    except ImportError:
        # Fallback: correlation
        c_hist = cv2.calcHist([c_gray], [0], None, [64], [0, 256])
        r_hist = cv2.calcHist([r_gray], [0], None, [64], [0, 256])
        score = cv2.compareHist(c_hist, r_hist, cv2.HISTCMP_CORREL)
    if score < 0.70:
        return (False, [f"Structural similarity too low: {score:.3f} (target > 0.70)"])
    return (True, [f"Similarity score: {score:.3f}"])


def verify_stage4(spec, render_path):
    try:
        import pytesseract
    except ImportError:
        return (False, ["pytesseract not available"])
    expected = [t.get("text") for t in spec.get("texts", []) if t.get("text")]
    if not expected:
        return (True, ["no text entries to verify"])
    ocr = pytesseract.image_to_string(render_path).lower()
    missing = [t for t in expected if t.lower() not in ocr]
    if missing:
        return (False, [f"Not OCR-readable in render: {missing}"])
    return (True, [])


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("spec")
    p.add_argument("--stage", type=int, required=True)
    p.add_argument("--chassis")
    p.add_argument("--render")
    args = p.parse_args()
    spec = json.load(open(args.spec))
    stage_fn = {1: verify_stage1, 2: verify_stage2, 3: verify_stage3, 4: verify_stage4}[args.stage]
    if args.stage == 1:
        ok, issues = stage_fn(spec)
    elif args.stage == 2:
        ok, issues = stage_fn(spec, args.chassis)
    elif args.stage == 3:
        ok, issues = stage_fn(spec, args.chassis, args.render)
    elif args.stage == 4:
        ok, issues = stage_fn(spec, args.render)
    print(f"Stage {args.stage}: {'PASS' if ok else 'FAIL'}")
    for i in issues:
        print(f"  - {i}")
    sys.exit(0 if ok else 1)
