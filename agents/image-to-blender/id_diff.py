"""
ID-pass pixel diff: render each element in a unique color, then find
exact centroids by color-matching. No ambiguity from overlapping shapes.

Usage:
    python3 id_diff.py <spec.json> <id_pass.png> <id_colors.json> [--out corrections.json]
"""
import json, argparse
import numpy as np
import cv2


def id_diff(spec_path, id_pass_path, id_colors_path):
    spec = json.load(open(spec_path))
    id_colors = json.load(open(id_colors_path))
    img = cv2.imread(id_pass_path)
    if img is None:
        raise SystemExit(f"Cannot read {id_pass_path}")

    h, w = img.shape[:2]
    # Convert id_colors from 0-1 float to 0-255 BGR for matching
    color_to_id = {}
    id_to_bgr = {}
    for eid, rgba in id_colors.items():
        if eid.startswith("keyboard_"):
            continue  # skip keyboard aggregate
        r, g, b = int(rgba[0] * 255), int(rgba[1] * 255), int(rgba[2] * 255)
        bgr = (b, g, r)
        color_to_id[bgr] = eid
        id_to_bgr[eid] = bgr

    # Build expected positions from spec
    expected = {}
    for k in spec.get("knobs", []):
        expected[k.get("id")] = {"cx": k["cx"], "cy": k["cy"], "cat": "knobs"}
    for s in spec.get("small_circles", []):
        expected[s.get("id")] = {"cx": s["cx"], "cy": s["cy"], "cat": "small_circles"}
    for r in spec.get("rectangles", []):
        cx = r.get("cx", r["x"] + r["w"] // 2)
        cy = r.get("cy", r["y"] + r["h"] // 2)
        expected[r.get("id")] = {"cx": cx, "cy": cy, "cat": "rectangles"}
    for t in spec.get("texts", []):
        cx = t.get("cx", t["x"] + t["w"] // 2)
        cy = t.get("cy", t["y"] + t["h"] // 2)
        expected[t.get("id")] = {"cx": cx, "cy": cy, "cat": "texts"}

    results = []
    corrections = []

    for eid, bgr in id_to_bgr.items():
        if eid not in expected:
            continue

        # Find all pixels matching this color (with tolerance for anti-aliasing)
        b, g, r = bgr
        lower = np.array([max(0, b-8), max(0, g-8), max(0, r-8)])
        upper = np.array([min(255, b+8), min(255, g+8), min(255, r+8)])
        mask = cv2.inRange(img, lower, upper)

        moments = cv2.moments(mask)
        if moments["m00"] < 5:
            results.append({"id": eid, "status": "NOT_FOUND", **expected[eid]})
            continue

        actual_cx = moments["m10"] / moments["m00"]
        actual_cy = moments["m01"] / moments["m00"]
        area = moments["m00"] / 255

        ex = expected[eid]["cx"]
        ey = expected[eid]["cy"]
        dx = actual_cx - ex
        dy = actual_cy - ey
        dist = (dx**2 + dy**2) ** 0.5

        results.append({
            "id": eid,
            "cat": expected[eid]["cat"],
            "status": "FOUND",
            "expected_cx": round(ex),
            "expected_cy": round(ey),
            "actual_cx": round(actual_cx, 1),
            "actual_cy": round(actual_cy, 1),
            "dx": round(dx, 1),
            "dy": round(dy, 1),
            "dist": round(dist, 1),
            "area": round(area),
        })

        if dist > 2:
            corrections.append({
                "element_id": eid,
                "field": "cx",
                "current": round(ex),
                "suggested": round(ex - dx),
            })
            corrections.append({
                "element_id": eid,
                "field": "cy",
                "current": round(ey),
                "suggested": round(ey - dy),
            })

    found = [r for r in results if r["status"] == "FOUND"]
    not_found = [r for r in results if r["status"] == "NOT_FOUND"]
    errors = [r["dist"] for r in found]

    summary = {
        "total": len(results),
        "found": len(found),
        "not_found": len(not_found),
        "avg_error_px": round(sum(errors) / max(len(errors), 1), 1),
        "max_error_px": round(max(errors, default=0), 1),
        "under_2px": sum(1 for e in errors if e <= 2),
        "under_3px": sum(1 for e in errors if e <= 3),
        "under_5px": sum(1 for e in errors if e <= 5),
        "corrections_needed": len(corrections) // 2,
    }

    return {"summary": summary, "elements": results, "corrections": corrections}


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("spec")
    p.add_argument("id_pass")
    p.add_argument("id_colors")
    p.add_argument("--out", default=None)
    args = p.parse_args()

    result = id_diff(args.spec, args.id_pass, args.id_colors)

    print(f"\n{'='*50}")
    print(f"  ID-PASS DIFF REPORT")
    print(f"{'='*50}")
    s = result["summary"]
    print(f"  Found: {s['found']}/{s['total']}")
    print(f"  Not found: {s['not_found']}")
    print(f"  Avg error: {s['avg_error_px']} px")
    print(f"  Max error: {s['max_error_px']} px")
    print(f"  Under 2px: {s['under_2px']}")
    print(f"  Under 3px: {s['under_3px']}")
    print(f"  Under 5px: {s['under_5px']}")
    print(f"  Corrections: {s['corrections_needed']}")

    worst = sorted([e for e in result["elements"] if e["status"] == "FOUND"],
                   key=lambda e: e["dist"], reverse=True)[:10]
    if worst:
        print(f"\n  WORST:")
        for e in worst:
            print(f"    {e['id']:25s}  dx={e['dx']:+6.1f}  dy={e['dy']:+6.1f}  dist={e['dist']:5.1f}px")

    not_found = [e for e in result["elements"] if e["status"] == "NOT_FOUND"]
    if not_found:
        print(f"\n  NOT FOUND: {[e['id'] for e in not_found]}")

    out = args.out or args.spec.replace(".json", ".iddiff.json")
    json.dump(result, open(out, "w"), indent=2)
    print(f"\n  Report → {out}")
