"""
Authoritative element list for Band Ritual Final 1, derived from
/Source/webui/index.html in the VST source. Instead of relying purely
on OpenCV detection (which is noisy), we use the ground-truth control
list and assign approximate positions on the 1619x971 chassis PNG.

Then OpenCV detection runs as a REFINEMENT pass — snapping each known
element's coord to the nearest detected blob, rather than trusting
the detector to identify the elements itself.

Produces the same JSON spec format as detect.py.
"""
import json
import sys


# 1619 × 971 canvas. All positions in image pixels.
# Layout matches the ChatGPT-generated mockup approximately.
AUTHORITATIVE_ELEMENTS = {
    "image_w": 1619,
    "image_h": 971,
    # --- HEADER BAR (y ≈ 20-60) ---
    "header": [
        {"id": "bypass",       "type": "toggle",     "cx": 265, "cy": 40,  "w": 70,  "h": 32},
        {"id": "title",        "type": "text",       "cx": 130, "cy": 35,  "w": 220, "h": 44, "text": "BAND RITUAL"},
        {"id": "trial_badge",  "type": "pill",       "cx": 360, "cy": 35,  "w": 70,  "h": 28, "color": "orange"},
        {"id": "info_btn",     "type": "small_btn",  "cx": 420, "cy": 40,  "w": 28,  "h": 28},
        {"id": "dist_tab",     "type": "pill",       "cx": 500, "cy": 40,  "w": 70,  "h": 32},
        {"id": "offset_tab",   "type": "pill",       "cx": 580, "cy": 40,  "w": 90,  "h": 32},
        {"id": "bands_tab",    "type": "pill",       "cx": 680, "cy": 40,  "w": 80,  "h": 32},
        {"id": "save_icon",    "type": "icon",       "cx": 790, "cy": 40,  "w": 36,  "h": 36},
        {"id": "preset_sel",   "type": "dropdown",   "cx": 900, "cy": 40,  "w": 100, "h": 32},
        {"id": "preset_ext",   "type": "dropdown",   "cx": 1170,"cy": 40,  "w": 200, "h": 32},
        {"id": "minimize",     "type": "small_btn",  "cx": 1520,"cy": 40,  "w": 34,  "h": 34},
        {"id": "close",        "type": "small_btn",  "cx": 1575,"cy": 40,  "w": 34,  "h": 34},
    ],

    # --- LEFT PANEL (x ≈ 20-270) ---
    "left_panel": [
        {"id": "mode_ritual",  "type": "dropdown",   "cx": 90,  "cy": 110, "w": 140, "h": 36},
        {"id": "mode_self",    "type": "dropdown",   "cx": 90,  "cy": 160, "w": 140, "h": 36},
        {"id": "q_knob",       "type": "small_knob", "cx": 215, "cy": 115, "r": 22},
        {"id": "mix_knob_big", "type": "big_knob",   "cx": 115, "cy": 290, "r": 70},   # hero knob
        {"id": "mix_slider",   "type": "vslider",    "cx": 230, "cy": 290, "w": 26,  "h": 140},
        {"id": "mix_label",    "type": "text",       "cx": 230, "cy": 360, "w": 36,  "h": 18, "text": "MIX"},
        {"id": "key_sel",      "type": "dropdown",   "cx": 75,  "cy": 430, "w": 80,  "h": 32},
        {"id": "scale_sel",    "type": "dropdown",   "cx": 180, "cy": 430, "w": 110, "h": 32},
        {"id": "m_indicator",  "type": "square_btn", "cx": 60,  "cy": 475, "w": 36,  "h": 36},
        {"id": "i_indicator",  "type": "square_btn", "cx": 100, "cy": 475, "w": 36,  "h": 36},
        {"id": "chord_type",   "type": "dropdown",   "cx": 180, "cy": 475, "w": 110, "h": 32},
        {"id": "tuning_btn",   "type": "pill_wide",  "cx": 145, "cy": 525, "w": 260, "h": 44, "color": "dark"},
    ],

    # --- CENTER SPECTRUM (x ≈ 275-1245) ---
    "center_panel": [
        {"id": "band_canvas",  "type": "display",    "cx": 760, "cy": 230, "w": 975, "h": 340, "color": "black"},
        {"id": "freq_left",    "type": "text",       "cx": 300, "cy": 75,  "w": 28,  "h": 16, "text": "20"},
        {"id": "freq_right",   "type": "text",       "cx": 1210,"cy": 75,  "w": 42,  "h": 16, "text": "20.0k"},
        {"id": "midi_btn",     "type": "small_btn",  "cx": 1205,"cy": 80,  "w": 44,  "h": 22},
        {"id": "freq_ax_l",    "type": "text",       "cx": 300, "cy": 400, "w": 28,  "h": 16, "text": "20"},
        {"id": "freq_ax_r",    "type": "text",       "cx": 1210,"cy": 400, "w": 42,  "h": 16, "text": "20.0k"},
    ],

    # --- MAIN KNOB ROW (mid, y ≈ 470-530) ---
    "main_knobs": [
        {"id": "bands_display","type": "digital",    "cx": 340, "cy": 495, "w": 110, "h": 56, "color": "dark"},
        {"id": "stack_btn",    "type": "pill_small", "cx": 410, "cy": 475, "w": 70,  "h": 24, "color": "green"},
        {"id": "bandCount",    "type": "knob",       "cx": 510, "cy": 495, "r": 34},
        {"id": "width",        "type": "knob",       "cx": 610, "cy": 495, "r": 34},
        {"id": "attack",       "type": "knob",       "cx": 710, "cy": 495, "r": 34},
        {"id": "release",      "type": "knob",       "cx": 810, "cy": 495, "r": 34},
        {"id": "gate",         "type": "knob",       "cx": 910, "cy": 495, "r": 34},
        {"id": "depth",        "type": "knob",       "cx": 1010,"cy": 495, "r": 34},
    ],

    # --- RIGHT PANEL (x ≈ 1280-1600) ---
    "right_panel": [
        {"id": "formant",      "type": "knob",       "cx": 1325,"cy": 110, "r": 32},
        {"id": "harmShift",    "type": "knob",       "cx": 1465,"cy": 110, "r": 32},
        {"id": "noise",        "type": "knob",       "cx": 1325,"cy": 200, "r": 32},
        {"id": "hpBlend",      "type": "knob",       "cx": 1465,"cy": 200, "r": 32},
        {"id": "hp_12db",      "type": "text",       "cx": 1500,"cy": 170, "w": 42,  "h": 16, "text": "12dB"},
        {"id": "noiseMode",    "type": "dropdown",   "cx": 1400,"cy": 275, "w": 110, "h": 30},
        {"id": "noiseColor",   "type": "knob",       "cx": 1395,"cy": 340, "r": 32},
    ],

    # --- TONE SCULPT SECTION (y ≈ 580-780) ---
    "tone_sculpt": [
        {"id": "eqPower",      "type": "big_btn",    "cx": 80,  "cy": 685, "r": 40, "color": "red"},
        {"id": "rainbow_dec",  "type": "decor",      "cx": 90,  "cy": 770, "w": 140, "h": 44},
        {"id": "eq_node_1",    "type": "eq_node",    "cx": 270, "cy": 685, "r": 16},
        {"id": "eq_node_2",    "type": "eq_node",    "cx": 600, "cy": 685, "r": 16},
        {"id": "eq_node_3",    "type": "eq_node",    "cx": 900, "cy": 685, "r": 16},
        {"id": "eq_node_4",    "type": "eq_node",    "cx": 1225,"cy": 685, "r": 16},
        {"id": "eq_n1_lbl",    "type": "text",       "cx": 260, "cy": 720, "w": 60,  "h": 16, "text": "20Hz"},
        {"id": "eq_n1_db",     "type": "text",       "cx": 260, "cy": 740, "w": 70,  "h": 16, "text": "48dB HP"},
        {"id": "eq_n2_lbl",    "type": "text",       "cx": 600, "cy": 720, "w": 60,  "h": 16, "text": "500Hz"},
        {"id": "eq_n3_lbl",    "type": "text",       "cx": 900, "cy": 720, "w": 40,  "h": 16, "text": "2.0k"},
        {"id": "eq_n4_lbl",    "type": "text",       "cx": 1225,"cy": 720, "w": 50,  "h": 16, "text": "20.0k"},
        {"id": "eq_n4_db",     "type": "text",       "cx": 1225,"cy": 740, "w": 60,  "h": 16, "text": "48dB LP"},
        {"id": "complement",   "type": "pill",       "cx": 1455,"cy": 605, "w": 110, "h": 32, "color": "red"},
        {"id": "freq_knob",    "type": "knob",       "cx": 1455,"cy": 670, "r": 26},
        {"id": "gain_knob",    "type": "knob",       "cx": 1455,"cy": 745, "r": 26},
    ],

    # --- KEYBOARD (bottom, y ≈ 800-960) ---
    "keyboard": {
        "x1": 40, "y1": 810, "x2": 1260, "y2": 955,
        "num_white": 14,
        "labels": ["C","D","E","F","G","A","B","C","D","E","F","G","A","B"],
    },
}


def flatten_to_spec(auth=AUTHORITATIVE_ELEMENTS):
    """Convert authoritative list into the detect.py JSON spec shape."""
    spec = {
        "image": "band_ritual_v2_chassis.png",
        "width": auth["image_w"],
        "height": auth["image_h"],
        "knobs": [],
        "small_circles": [],
        "rectangles": [],
        "color_regions": [],
        "spectrum_strip": None,
        "keyboard_strip": None,
        "texts": [],
        "authoritative": [],
    }
    groups = ["header", "left_panel", "center_panel", "main_knobs",
              "right_panel", "tone_sculpt"]
    for g in groups:
        for e in auth.get(g, []):
            entry = {"group": g, **e}
            spec["authoritative"].append(entry)
            t = e["type"]
            if t in ("knob", "big_knob", "small_knob"):
                r = e.get("r", 30)
                spec["knobs"].append({"cx": e["cx"], "cy": e["cy"], "r": r, "id": e["id"]})
            elif t in ("eq_node", "big_btn"):
                r = e.get("r", 16)
                spec["small_circles"].append({"cx": e["cx"], "cy": e["cy"], "r": r, "id": e["id"]})
            elif t in ("pill", "pill_wide", "pill_small", "dropdown",
                       "square_btn", "small_btn", "toggle", "icon",
                       "digital", "vslider", "display", "decor"):
                x = e["cx"] - e["w"] // 2
                y = e["cy"] - e["h"] // 2
                spec["rectangles"].append({
                    "x": x, "y": y, "w": e["w"], "h": e["h"],
                    "kind": t, "id": e["id"],
                })
            elif t == "text":
                spec["texts"].append({
                    "text": e.get("text", ""),
                    "x": e["cx"] - e["w"] // 2, "y": e["cy"] - e["h"] // 2,
                    "w": e["w"], "h": e["h"], "id": e["id"],
                })
    # Keyboard
    kb = auth.get("keyboard")
    if kb:
        spec["keyboard_strip"] = {"x1": kb["x1"], "y1": kb["y1"], "x2": kb["x2"], "y2": kb["y2"]}
    # Spectrum strip = band_canvas rect
    bc = next((e for g in groups for e in auth.get(g, []) if e.get("id") == "band_canvas"), None)
    if bc:
        spec["spectrum_strip"] = {
            "x1": bc["cx"] - bc["w"] // 2,
            "y1": bc["cy"] - bc["h"] // 2,
            "x2": bc["cx"] + bc["w"] // 2,
            "y2": bc["cy"] + bc["h"] // 2,
        }
    return spec


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "/Users/ricosan/Downloads/v2_authoritative.json"
    spec = flatten_to_spec()
    with open(out, "w") as f:
        json.dump(spec, f, indent=2)
    print(f"Wrote {out}")
    print(f"Elements: knobs={len(spec['knobs'])}, small={len(spec['small_circles'])}, "
          f"rects={len(spec['rectangles'])}, texts={len(spec['texts'])}")
