"""
Pixel-level diff scoring: render each element as a mask, find its centroid
in both the render and the chassis PNG, compute displacement vectors.

Returns per-element dx/dy errors and auto-generates corrections.

Usage:
    python3 pixel_diff.py <spec.json> <chassis.png> <render.png> [--out corrections.json]
"""
import json, argparse, sys
import numpy as np
import cv2


def _spec_mask(spec, img_shape):
    """Create per-element masks from the spec coordinates."""
    h, w = img_shape[:2]
    elements = []

    for k in spec.get("knobs", []):
        mask = np.zeros((h, w), dtype=np.uint8)
        cv2.circle(mask, (int(k["cx"]), int(k["cy"])), int(k["r"]), 255, -1)
        elements.append({"id": k.get("id", "?"), "cat": "knobs", "mask": mask,
                         "expected_cx": k["cx"], "expected_cy": k["cy"],
                         "expected_r": k.get("r", 30)})

    for s in spec.get("small_circles", []):
        mask = np.zeros((h, w), dtype=np.uint8)
        cv2.circle(mask, (int(s["cx"]), int(s["cy"])), int(s["r"]), 255, -1)
        elements.append({"id": s.get("id", "?"), "cat": "small_circles", "mask": mask,
                         "expected_cx": s["cx"], "expected_cy": s["cy"],
                         "expected_r": s.get("r", 16)})

    for r in spec.get("rectangles", []):
        mask = np.zeros((h, w), dtype=np.uint8)
        x, y, rw, rh = int(r["x"]), int(r["y"]), int(r["w"]), int(r["h"])
        cv2.rectangle(mask, (max(0, x), max(0, y)),
                      (min(w, x + rw), min(h, y + rh)), 255, -1)
        elements.append({"id": r.get("id", "?"), "cat": "rectangles", "mask": mask,
                         "expected_cx": x + rw // 2, "expected_cy": y + rh // 2,
                         "expected_w": rw, "expected_h": rh})

    for t in spec.get("texts", []):
        mask = np.zeros((h, w), dtype=np.uint8)
        x, y, tw, th = int(t["x"]), int(t["y"]), int(t["w"]), int(t["h"])
        cv2.rectangle(mask, (max(0, x), max(0, y)),
                      (min(w, x + tw), min(h, y + th)), 255, -1)
        elements.append({"id": t.get("id", "?"), "cat": "texts", "mask": mask,
                         "expected_cx": x + tw // 2, "expected_cy": y + th // 2})

    return elements


def _find_rendered_centroid(render_gray, bg_gray, mask, threshold=15):
    """Find where the element actually rendered by diffing render vs background.

    Returns (cx, cy, area) or None if element not found.
    """
    # Absolute diff between render and a uniform background
    diff = cv2.absdiff(render_gray, bg_gray)

    # Only look within the mask region (expanded slightly for tolerance)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (21, 21))
    expanded_mask = cv2.dilate(mask, kernel, iterations=2)

    # Pixels that differ from background within the search region
    search = cv2.bitwise_and(diff, diff, mask=expanded_mask)
    _, binary = cv2.threshold(search, threshold, 255, cv2.THRESH_BINARY)

    # Find centroid of the detected pixels
    moments = cv2.moments(binary)
    if moments["m00"] < 10:  # too few pixels
        return None

    cx = moments["m10"] / moments["m00"]
    cy = moments["m01"] / moments["m00"]
    area = moments["m00"] / 255
    return (cx, cy, area)


def _estimate_background(render):
    """Estimate the background color (most common color along borders)."""
    h, w = render.shape[:2]
    border_pixels = np.concatenate([
        render[0, :],        # top row
        render[h-1, :],      # bottom row
        render[:, 0],        # left col
        render[:, w-1],      # right col
    ])
    bg_color = np.median(border_pixels, axis=0).astype(np.uint8)
    bg = np.full_like(render, bg_color)
    return cv2.cvtColor(bg, cv2.COLOR_BGR2GRAY)


def pixel_diff(spec_path, chassis_path, render_path):
    """Compare render against spec positions. Returns per-element errors."""
    spec = json.load(open(spec_path))
    chassis = cv2.imread(chassis_path)
    render = cv2.imread(render_path)

    if chassis is None:
        raise SystemExit(f"Cannot read chassis: {chassis_path}")
    if render is None:
        raise SystemExit(f"Cannot read render: {render_path}")

    # Resize render to chassis dimensions if needed
    ch, cw = chassis.shape[:2]
    if render.shape[:2] != (ch, cw):
        render = cv2.resize(render, (cw, ch))

    render_gray = cv2.cvtColor(render, cv2.COLOR_BGR2GRAY)
    bg_gray = _estimate_background(render)

    elements = _spec_mask(spec, chassis.shape)
    results = []
    total_error = 0
    found = 0

    for elem in elements:
        centroid = _find_rendered_centroid(render_gray, bg_gray, elem["mask"])
        if centroid is None:
            results.append({
                "id": elem["id"],
                "cat": elem["cat"],
                "status": "NOT_FOUND",
                "expected_cx": elem["expected_cx"],
                "expected_cy": elem["expected_cy"],
            })
            continue

        actual_cx, actual_cy, area = centroid
        dx = actual_cx - elem["expected_cx"]
        dy = actual_cy - elem["expected_cy"]
        dist = (dx**2 + dy**2) ** 0.5

        results.append({
            "id": elem["id"],
            "cat": elem["cat"],
            "status": "FOUND",
            "expected_cx": round(elem["expected_cx"]),
            "expected_cy": round(elem["expected_cy"]),
            "actual_cx": round(actual_cx),
            "actual_cy": round(actual_cy),
            "dx": round(dx, 1),
            "dy": round(dy, 1),
            "dist": round(dist, 1),
            "area": round(area),
        })
        total_error += dist
        found += 1

    # Generate corrections for elements with >3px error
    corrections = []
    for r in results:
        if r["status"] != "FOUND":
            continue
        if r["dist"] > 3:
            corrections.append({
                "element_id": r["id"],
                "field": "cx",
                "current": r["expected_cx"],
                "suggested": r["expected_cx"] - round(r["dx"]),
                "reason": f"render offset dx={r['dx']}, dy={r['dy']} ({r['dist']}px)",
            })
            corrections.append({
                "element_id": r["id"],
                "field": "cy",
                "current": r["expected_cy"],
                "suggested": r["expected_cy"] - round(r["dy"]),
                "reason": f"render offset dx={r['dx']}, dy={r['dy']} ({r['dist']}px)",
            })

    avg_error = total_error / max(found, 1)
    summary = {
        "total_elements": len(elements),
        "found": found,
        "not_found": len(elements) - found,
        "avg_error_px": round(avg_error, 1),
        "max_error_px": round(max((r["dist"] for r in results if r["status"] == "FOUND"), default=0), 1),
        "elements_under_3px": sum(1 for r in results if r["status"] == "FOUND" and r["dist"] <= 3),
        "elements_under_5px": sum(1 for r in results if r["status"] == "FOUND" and r["dist"] <= 5),
        "corrections_needed": len(corrections) // 2,  # cx+cy pairs
    }

    return {"summary": summary, "elements": results, "corrections": corrections}


def generate_debug_image(spec_path, chassis_path, render_path, out_path):
    """Draw arrows showing displacement from expected to actual position."""
    spec = json.load(open(spec_path))
    chassis = cv2.imread(chassis_path)
    render = cv2.imread(render_path)
    ch, cw = chassis.shape[:2]
    if render.shape[:2] != (ch, cw):
        render = cv2.resize(render, (cw, ch))

    # Blend chassis + render 50/50
    debug = cv2.addWeighted(chassis, 0.5, render, 0.5, 0)

    render_gray = cv2.cvtColor(render, cv2.COLOR_BGR2GRAY)
    bg_gray = _estimate_background(render)
    elements = _spec_mask(spec, chassis.shape)

    for elem in elements:
        ex, ey = int(elem["expected_cx"]), int(elem["expected_cy"])
        centroid = _find_rendered_centroid(render_gray, bg_gray, elem["mask"])

        if centroid is None:
            # Red X for missing
            cv2.drawMarker(debug, (ex, ey), (0, 0, 255), cv2.MARKER_TILTED_CROSS, 20, 2)
            continue

        ax, ay = int(centroid[0]), int(centroid[1])
        dist = ((ex - ax)**2 + (ey - ay)**2) ** 0.5

        if dist <= 3:
            # Green dot: good
            cv2.circle(debug, (ex, ey), 5, (0, 255, 0), -1)
        elif dist <= 10:
            # Yellow arrow: minor offset
            cv2.arrowedLine(debug, (ax, ay), (ex, ey), (0, 255, 255), 2)
        else:
            # Red arrow: major offset
            cv2.arrowedLine(debug, (ax, ay), (ex, ey), (0, 0, 255), 2)

    cv2.imwrite(out_path, debug)
    print(f"Debug overlay → {out_path}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("spec")
    p.add_argument("chassis")
    p.add_argument("render")
    p.add_argument("--out", default=None)
    p.add_argument("--debug-img", default=None, help="Write debug overlay image")
    args = p.parse_args()

    result = pixel_diff(args.spec, args.chassis, args.render)

    print(f"\n{'='*50}")
    print(f"  PIXEL DIFF REPORT")
    print(f"{'='*50}")
    s = result["summary"]
    print(f"  Found: {s['found']}/{s['total_elements']}")
    print(f"  Not found: {s['not_found']}")
    print(f"  Avg error: {s['avg_error_px']} px")
    print(f"  Max error: {s['max_error_px']} px")
    print(f"  Under 3px: {s['elements_under_3px']}")
    print(f"  Under 5px: {s['elements_under_5px']}")
    print(f"  Corrections needed: {s['corrections_needed']}")

    # Print worst offenders
    worst = sorted([e for e in result["elements"] if e["status"] == "FOUND"],
                   key=lambda e: e["dist"], reverse=True)[:10]
    if worst:
        print(f"\n  WORST OFFENDERS:")
        for e in worst:
            print(f"    {e['id']:25s}  dx={e['dx']:+6.1f}  dy={e['dy']:+6.1f}  dist={e['dist']:5.1f}px")

    not_found = [e for e in result["elements"] if e["status"] == "NOT_FOUND"]
    if not_found:
        print(f"\n  NOT FOUND:")
        for e in not_found:
            print(f"    {e['id']}")

    out = args.out or args.spec.replace(".json", ".pixdiff.json")
    json.dump(result, open(out, "w"), indent=2)
    print(f"\n  Full report → {out}")

    if args.debug_img:
        generate_debug_image(args.spec, args.chassis, args.render, args.debug_img)
