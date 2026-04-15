"""
Stage 2.5 polish: meticulous alignment + symmetry + centering pass.

Takes a refined.json and applies design-rules:
  - Rows of equivalent elements share Y and have equal spacing
  - Rows of equivalent elements share radius/size
  - Labels sit directly under their controls (same cx)
  - Paired left/right elements mirror symmetrically around a panel center
  - Groups center within their section bounding box

Usage:
    python3 polish.py <refined.json> --out <polished.json>
"""
import json
import sys
import argparse


def _align_row(elements, key_cy="cy", equal_r=True):
    """Set all elements in a row to the average Y, optionally equal radius."""
    if not elements:
        return
    avg_cy = sum(e[key_cy] for e in elements) // len(elements)
    for e in elements:
        e[key_cy] = avg_cy
    if equal_r and all("r" in e for e in elements):
        avg_r = sum(e["r"] for e in elements) // len(elements)
        for e in elements:
            e["r"] = avg_r


def _equal_spacing(elements, x_start, x_end, key_cx="cx"):
    """Distribute elements with equal spacing across x_start..x_end."""
    n = len(elements)
    if n == 1:
        elements[0][key_cx] = (x_start + x_end) // 2
        return
    step = (x_end - x_start) / (n - 1)
    for i, e in enumerate(elements):
        e[key_cx] = int(x_start + i * step)


def _symmetric_pair(left, right, center_x):
    """Mirror two elements around a vertical axis."""
    dx = (abs(left["cx"] - center_x) + abs(right["cx"] - center_x)) // 2
    left["cx"] = center_x - dx
    right["cx"] = center_x + dx


def _center_label_under(label, control, y_offset=50):
    """Position label directly under the control on the same X."""
    label["x"] = control["cx"] - label["w"] // 2
    label["y"] = control["cy"] + y_offset


def _ensure_cxcy(e):
    """Rectangles have x,y,w,h but no cx,cy. Add them."""
    if "cx" not in e and "x" in e and "w" in e:
        e["cx"] = e["x"] + e["w"] // 2
    if "cy" not in e and "y" in e and "h" in e:
        e["cy"] = e["y"] + e["h"] // 2
    return e


def polish(spec):
    # Index by ID for easy lookup; ensure cx/cy on rectangles and texts
    by_id = {}
    for cat in ("knobs", "small_circles", "rectangles", "texts"):
        for e in spec.get(cat, []):
            _ensure_cxcy(e)
            if "id" in e:
                by_id[e["id"]] = (cat, e)

    W = spec["width"]
    HEIGHT = spec["height"]
    CENTER_X = W // 2
    RIGHT_PANEL_CX = 1385  # midpoint of the right panel

    # --- HEADER: all same Y ---
    header_ids = ["title_band_ritual", "trial_badge", "info_icon",
                  "dist_tab", "offset_tab", "bands_tab", "save_btn",
                  "preset_init", "preset_ext", "minimize_btn", "close_btn"]
    header_els = [by_id[i][1] for i in header_ids if i in by_id]
    HDR_Y = 37
    for e in header_els:
        if "cy" in e: e["cy"] = HDR_Y
        if "y" in e and "h" in e: e["y"] = HDR_Y - e["h"] // 2

    # --- LEFT PANEL ---
    # Ritual + Self same cx (stacked column), spaced vertically
    if "mode_ritual" in by_id and "mode_self" in by_id:
        r = by_id["mode_ritual"][1]
        s = by_id["mode_self"][1]
        common_cx = (r["cx"] + s["cx"]) // 2
        r["cx"] = common_cx; s["cx"] = common_cx
        # Update 'x' for rectangles
        if by_id["mode_ritual"][0] == "rectangles":
            r["x"] = r["cx"] - r["w"] // 2
        if by_id["mode_self"][0] == "rectangles":
            s["x"] = s["cx"] - s["w"] // 2
    # Scale row 1 and row 2: same column cx between keySelect↔chordDegree_M, scaleType↔chordType
    if "keySelect" in by_id and "chordType" in by_id:
        k = by_id["keySelect"][1]
        ct = by_id["chordType"][1]
        # Nothing to align horizontally; just enforce same column logic if desired
    # MIX knob + slider share same Y (midline)
    if "mix_knob_hero" in by_id and "mix_slider" in by_id:
        k = by_id["mix_knob_hero"][1]
        s = by_id["mix_slider"][1]
        common_cy = (k["cy"] + s["cy"]) // 2
        k["cy"] = common_cy
        s["cy"] = common_cy
        if by_id["mix_slider"][0] == "rectangles":
            s["y"] = s["cy"] - s["h"] // 2
    # MIX label centered under slider
    if "mix_label" in by_id and "mix_slider" in by_id:
        l = by_id["mix_label"][1]
        s = by_id["mix_slider"][1]
        l["x"] = s["cx"] - l["w"] // 2

    # --- MAIN KNOB ROW: bandCount/width/attack/release/gate/depth ---
    knob_ids = ["width", "attack", "release", "gate", "depth"]
    knob_els = [by_id[i][1] for i in knob_ids if i in by_id]
    if len(knob_els) == 5:
        _align_row(knob_els, equal_r=True)
        # Equal spacing across range
        _equal_spacing(knob_els, 530, 1010)
    # Knob labels: align to knobs
    label_ids = ["widthLabel", "attackLabel", "releaseLabel", "gateLabel", "depthLabel"]
    for kid, lid in zip(knob_ids, label_ids):
        if kid in by_id and lid in by_id:
            k = by_id[kid][1]
            l = by_id[lid][1]
            l["x"] = k["cx"] - l["w"] // 2
            l["y"] = k["cy"] + k["r"] + 10

    # --- RIGHT PANEL: symmetric pairs around RIGHT_PANEL_CX ---
    if "formantKnob" in by_id and "harmShiftKnob" in by_id:
        f = by_id["formantKnob"][1]; h = by_id["harmShiftKnob"][1]
        _align_row([f, h], equal_r=True)
        _symmetric_pair(f, h, RIGHT_PANEL_CX)
    if "noiseKnob" in by_id and "hpBlendKnob" in by_id:
        n = by_id["noiseKnob"][1]; hb = by_id["hpBlendKnob"][1]
        _align_row([n, hb], equal_r=True)
        _symmetric_pair(n, hb, RIGHT_PANEL_CX)
    # Labels under their knobs
    rp_pairs = [("formantKnob", "formantLabel"), ("harmShiftKnob", "harmShiftLabel"),
                ("noiseKnob", "noiseLabel"), ("hpBlendKnob", "hpBlendLabel"),
                ("noiseColorKnob", "noiseColorLabel")]
    for kid, lid in rp_pairs:
        if kid in by_id and lid in by_id:
            k = by_id[kid][1]; l = by_id[lid][1]
            l["x"] = k["cx"] - l["w"] // 2
            l["y"] = k["cy"] + k["r"] + 8
    # noiseMode dropdown + noiseColor centered on right panel center
    if "noiseColorKnob" in by_id:
        by_id["noiseColorKnob"][1]["cx"] = RIGHT_PANEL_CX
    if "noiseMode" in by_id:
        nm = by_id["noiseMode"][1]
        nm["cx"] = RIGHT_PANEL_CX
        nm["x"] = nm["cx"] - nm["w"] // 2

    # --- EQ NODES: same Y, evenly spaced ---
    eq_ids = ["eq_node_1", "eq_node_2", "eq_node_3", "eq_node_4"]
    eq_els = [by_id[i][1] for i in eq_ids if i in by_id]
    if len(eq_els) == 4:
        _align_row(eq_els, equal_r=True)
        _equal_spacing(eq_els, 225, 1240)
    # EQ freq labels under their nodes
    eq_lbl_pairs = [("eq_node_1", ["eq1_freq_lbl", "eq1_db_lbl"]),
                    ("eq_node_2", ["eq2_freq_lbl", "eq2_db_lbl"]),
                    ("eq_node_3", ["eq3_freq_lbl", "eq3_db_lbl"]),
                    ("eq_node_4", ["eq4_freq_lbl", "eq4_db_lbl"])]
    for nid, labels in eq_lbl_pairs:
        if nid not in by_id: continue
        n = by_id[nid][1]
        for j, lid in enumerate(labels):
            if lid in by_id:
                l = by_id[lid][1]
                l["x"] = n["cx"] - l["w"] // 2
                l["y"] = n["cy"] + n["r"] + 8 + j * 22

    # --- EQ-right column: freqKnob, gainKnob, qEqKnob all same cx ---
    col_ids = ["freqKnob", "gainKnob", "qEqKnob"]
    col_els = [by_id[i][1] for i in col_ids if i in by_id]
    if col_els:
        avg_cx = sum(e["cx"] for e in col_els) // len(col_els)
        for e in col_els:
            e["cx"] = avg_cx
    col_pairs = [("freqKnob", "freqLabel"), ("gainKnob", "gainLabel"), ("qEqKnob", "qEqLabel")]
    for kid, lid in col_pairs:
        if kid in by_id and lid in by_id:
            k = by_id[kid][1]; l = by_id[lid][1]
            l["x"] = k["cx"] - l["w"] // 2
            l["y"] = k["cy"] + k["r"] + 6

    # --- Rewrite rectangle x,y from updated cx,cy ---
    for cat in ("rectangles",):
        for e in spec.get(cat, []):
            if "cx" in e and "cy" in e:
                e["x"] = e["cx"] - e["w"] // 2
                e["y"] = e["cy"] - e["h"] // 2

    return spec


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("spec")
    p.add_argument("--out", default=None)
    args = p.parse_args()
    spec = json.load(open(args.spec))
    spec = polish(spec)
    out = args.out or args.spec.replace(".json", ".polished.json")
    json.dump(spec, open(out, "w"), indent=2)
    print(f"Polished: {out}")
