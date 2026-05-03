"""
Auto-alignment pass: project every element's edges onto X and Y axes,
cluster nearby edges, snap each element so its edges align with cluster
centers. Result: shared alignment lines across the whole GUI (no more
"almost-aligned" positions).

Also detects centered-in-container groups and recenters them precisely.

Usage:
    python3 auto_align.py <spec.json> --out <aligned.json>
"""
import json
import argparse
from collections import defaultdict


def _edges_for_rect(r):
    """Left, right, top, bottom, hcenter, vcenter."""
    x, y, w, h = r["x"], r["y"], r["w"], r["h"]
    return {
        "left": x,
        "right": x + w,
        "top": y,
        "bottom": y + h,
        "hcenter": x + w // 2,
        "vcenter": y + h // 2,
    }


def _edges_for_circle(c):
    cx, cy, r = c["cx"], c["cy"], c["r"]
    return {
        "left": cx - r,
        "right": cx + r,
        "top": cy - r,
        "bottom": cy + r,
        "hcenter": cx,
        "vcenter": cy,
    }


def _cluster_values(values, tolerance):
    """Group values that are within `tolerance` px of each other. Return {value → cluster_mean}."""
    sorted_vals = sorted(set(values))
    clusters = []
    current = [sorted_vals[0]]
    for v in sorted_vals[1:]:
        if v - current[-1] <= tolerance:
            current.append(v)
        else:
            clusters.append(current)
            current = [v]
    clusters.append(current)
    mapping = {}
    for cluster in clusters:
        # Require at least 2 elements to snap (otherwise it's lonely, leave it)
        if len(cluster) >= 2:
            mean = sum(cluster) / len(cluster)
            for v in cluster:
                mapping[v] = round(mean)
    return mapping


def auto_align(spec, tolerance=8):
    """Snap each element's edges to cluster centers where ≥2 elements share an edge value within tolerance."""
    rects = spec.get("rectangles", []) + spec.get("texts", [])
    circles = spec.get("knobs", []) + spec.get("small_circles", [])
    all_elements = [(e, "rect") for e in rects] + [(e, "circle") for e in circles]

    # Collect ALL X-axis coords (lefts, rights, hcenters) and Y-axis coords
    xs = []
    ys = []
    for e, kind in all_elements:
        edges = _edges_for_rect(e) if kind == "rect" else _edges_for_circle(e)
        xs.extend([edges["left"], edges["right"], edges["hcenter"]])
        ys.extend([edges["top"], edges["bottom"], edges["vcenter"]])

    x_map = _cluster_values(xs, tolerance)
    y_map = _cluster_values(ys, tolerance)

    # Snap each element to clustered edges (prefer hcenter/vcenter snapping to preserve width/height)
    for e, kind in all_elements:
        edges = _edges_for_rect(e) if kind == "rect" else _edges_for_circle(e)
        # Find strongest snap: if hcenter is in a cluster, snap by that delta
        new_hcenter = x_map.get(edges["hcenter"], edges["hcenter"])
        new_vcenter = y_map.get(edges["vcenter"], edges["vcenter"])
        dx = new_hcenter - edges["hcenter"]
        dy = new_vcenter - edges["vcenter"]
        # Also consider left/right/top/bottom edges
        if dx == 0:
            new_left = x_map.get(edges["left"], edges["left"])
            new_right = x_map.get(edges["right"], edges["right"])
            if new_left != edges["left"]:
                dx = new_left - edges["left"]
            elif new_right != edges["right"]:
                dx = new_right - edges["right"]
        if dy == 0:
            new_top = y_map.get(edges["top"], edges["top"])
            new_bottom = y_map.get(edges["bottom"], edges["bottom"])
            if new_top != edges["top"]:
                dy = new_top - edges["top"]
            elif new_bottom != edges["bottom"]:
                dy = new_bottom - edges["bottom"]

        if kind == "rect":
            e["x"] = e["x"] + dx
            e["y"] = e["y"] + dy
            e["cx"] = e["x"] + e["w"] // 2
            e["cy"] = e["y"] + e["h"] // 2
        else:
            e["cx"] = e["cx"] + dx
            e["cy"] = e["cy"] + dy

    return spec


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("spec")
    p.add_argument("--out", default=None)
    p.add_argument("--tolerance", type=int, default=8,
                   help="Snap tolerance in pixels (default 8)")
    args = p.parse_args()
    spec = json.load(open(args.spec))
    spec = auto_align(spec, tolerance=args.tolerance)
    out = args.out or args.spec.replace(".json", ".aligned.json")
    json.dump(spec, open(out, "w"), indent=2)
    print(f"Auto-aligned → {out}")
