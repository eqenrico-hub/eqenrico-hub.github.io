"""
Authoritative element list for Band Ritual V2 (ChatGPT-designed chassis).

Key principle: PNG is ground truth for VISUAL layout. HTML is context
for parameter names / meaning only. Every position here is measured
by visual inspection of band_ritual_v2_chassis.png (1619 × 971).

Includes decorative elements visible in the PNG that don't exist in
Final 1 HTML (trial badge, tabs, rainbow, piano keys, etc.). These
ship with the cosmetic chassis and must be rebuilt for a standalone
3D scene to match visually.
"""
import json
import sys


AUTHORITATIVE_ELEMENTS = {
    "image_w": 1619,
    "image_h": 971,

    # ============================================================
    # HEADER (y ≈ 10-55)
    # ============================================================
    "header": [
        {"id": "title_band_ritual", "type": "text",      "cx": 145,  "cy": 32,  "w": 250, "h": 45,  "text": "BAND RITUAL"},
        {"id": "trial_badge",       "type": "pill",      "cx": 330,  "cy": 37,  "w": 80,  "h": 25},
        {"id": "info_icon",         "type": "small_btn", "cx": 390,  "cy": 37,  "w": 28,  "h": 28},
        {"id": "dist_tab",          "type": "pill",      "cx": 485,  "cy": 37,  "w": 80,  "h": 26},
        {"id": "offset_tab",        "type": "pill",      "cx": 590,  "cy": 37,  "w": 100, "h": 26},
        {"id": "bands_tab",         "type": "pill",      "cx": 705,  "cy": 37,  "w": 100, "h": 26},
        {"id": "save_btn",          "type": "small_btn", "cx": 820,  "cy": 37,  "w": 36,  "h": 34},
        {"id": "preset_init",       "type": "dropdown",  "cx": 925,  "cy": 37,  "w": 120, "h": 26},
        {"id": "preset_ext",        "type": "dropdown",  "cx": 1220, "cy": 37,  "w": 440, "h": 26},
        {"id": "minimize_btn",      "type": "small_btn", "cx": 1500, "cy": 37,  "w": 32,  "h": 32},
        {"id": "close_btn",         "type": "small_btn", "cx": 1555, "cy": 37,  "w": 32,  "h": 32},
    ],

    # ============================================================
    # LEFT PANEL (x ≈ 10-335)
    # ============================================================
    "left_panel": [
        # MODE dropdowns (Ritual / Self)
        {"id": "mode_ritual",   "type": "dropdown",  "cx": 100, "cy": 100, "w": 150, "h": 40},
        {"id": "mode_self",     "type": "dropdown",  "cx": 100, "cy": 150, "w": 150, "h": 40},
        {"id": "q_knob",        "type": "small_knob","cx": 230, "cy": 110, "r": 30},
        {"id": "q_label",       "type": "text",      "cx": 230, "cy": 150, "w": 30,  "h": 16, "text": "Q"},
        # HERO knob + MIX slider
        {"id": "mix_knob_hero", "type": "big_knob",  "cx": 135, "cy": 250, "r": 95},
        {"id": "mix_slider",    "type": "vslider",   "cx": 245, "cy": 250, "w": 40,  "h": 165},
        {"id": "mix_label",     "type": "text",      "cx": 245, "cy": 345, "w": 50,  "h": 20, "text": "MIX"},
        # Scale row 1
        {"id": "keySelect",     "type": "dropdown",  "cx": 80,  "cy": 407, "w": 80,  "h": 35},
        {"id": "scaleType",     "type": "dropdown",  "cx": 200, "cy": 407, "w": 130, "h": 35},
        {"id": "scale_color",   "type": "color_ind", "cx": 280, "cy": 407, "w": 22,  "h": 32},
        # Scale row 2
        {"id": "chordDegree_M", "type": "square_btn","cx": 60,  "cy": 457, "w": 40,  "h": 35, "text": "M"},
        {"id": "chordDegree_I", "type": "square_btn","cx": 105, "cy": 457, "w": 40,  "h": 35, "text": "I"},
        {"id": "chordType",     "type": "dropdown",  "cx": 200, "cy": 457, "w": 130, "h": 35},
        # TUNING full-width button
        {"id": "tuning_btn",    "type": "pill_wide", "cx": 165, "cy": 515, "w": 280, "h": 50},
    ],

    # ============================================================
    # CENTER — band visualizer + vocoder knob row
    # ============================================================
    "center_panel": [
        # Big spectrum display (dark with vertical colored bars painted in PNG)
        {"id": "bandCanvas",        "type": "display",  "cx": 790,  "cy": 220, "w": 970, "h": 320, "color": "black"},
        {"id": "freq_left_top",     "type": "text",     "cx": 335,  "cy": 80,  "w": 28,  "h": 16, "text": "20"},
        {"id": "freq_right_top",    "type": "text",     "cx": 1230, "cy": 80,  "w": 50,  "h": 16, "text": "20.0k"},
        {"id": "midi_btn",          "type": "pill",     "cx": 1155, "cy": 80,  "w": 52,  "h": 22, "text": "MIDI"},
        {"id": "freq_left_bot",     "type": "text",     "cx": 330,  "cy": 340, "w": 28,  "h": 16, "text": "20"},
        {"id": "freq_right_bot",    "type": "text",     "cx": 1225, "cy": 340, "w": 50,  "h": 16, "text": "20.0k"},
        # Number display boxes
        {"id": "bandCount_display", "type": "digital", "cx": 390, "cy": 493, "w": 100, "h": 45, "text": "70"},
        {"id": "stack_pill",        "type": "pill",     "cx": 485, "cy": 483, "w": 70,  "h": 22, "text": "STACK"},
        {"id": "bandCount_sub",     "type": "text",     "cx": 390, "cy": 528, "w": 85,  "h": 28, "text": "→ 70"},
        # Knob row
        {"id": "width",             "type": "knob",     "cx": 530, "cy": 495, "r": 40},
        {"id": "attack",            "type": "knob",     "cx": 650, "cy": 495, "r": 40},
        {"id": "release",           "type": "knob",     "cx": 770, "cy": 495, "r": 40},
        {"id": "gate",              "type": "knob",     "cx": 890, "cy": 495, "r": 40},
        {"id": "depth",             "type": "knob",     "cx": 1010,"cy": 495, "r": 40},
        # Labels under knobs
        {"id": "widthLabel",        "type": "text",     "cx": 530, "cy": 550, "w": 60,  "h": 16, "text": "width"},
        {"id": "attackLabel",       "type": "text",     "cx": 650, "cy": 550, "w": 60,  "h": 16, "text": "attack"},
        {"id": "releaseLabel",      "type": "text",     "cx": 770, "cy": 550, "w": 70,  "h": 16, "text": "release"},
        {"id": "gateLabel",         "type": "text",     "cx": 890, "cy": 550, "w": 60,  "h": 16, "text": "gate"},
        {"id": "depthLabel",        "type": "text",     "cx": 1010,"cy": 550, "w": 60,  "h": 16, "text": "depth"},
    ],

    # ============================================================
    # RIGHT PANEL (x ≈ 1275-1620)
    # ============================================================
    "right_panel": [
        {"id": "formantKnob",     "type": "knob",     "cx": 1315, "cy": 100, "r": 35},
        {"id": "formantLabel",    "type": "text",     "cx": 1315, "cy": 150, "w": 70,  "h": 16, "text": "formant"},
        {"id": "harmShiftKnob",   "type": "knob",     "cx": 1450, "cy": 100, "r": 35},
        {"id": "harmShiftLabel",  "type": "text",     "cx": 1450, "cy": 150, "w": 90,  "h": 16, "text": "Harm Shift"},
        {"id": "noiseKnob",       "type": "knob",     "cx": 1315, "cy": 180, "r": 35},
        {"id": "noiseLabel",      "type": "text",     "cx": 1315, "cy": 230, "w": 60,  "h": 16, "text": "noise"},
        {"id": "hpBlendKnob",     "type": "knob",     "cx": 1450, "cy": 180, "r": 35},
        {"id": "hpBlendLabel",    "type": "text",     "cx": 1450, "cy": 230, "w": 80,  "h": 16, "text": "hp-blend"},
        {"id": "hp12db",          "type": "text",     "cx": 1510, "cy": 160, "w": 40,  "h": 14, "text": "12dB"},
        {"id": "noiseMode",       "type": "dropdown", "cx": 1390, "cy": 255, "w": 90,  "h": 28},
        {"id": "noiseColorKnob",  "type": "knob",     "cx": 1450, "cy": 310, "r": 35},
        {"id": "noiseColorLabel", "type": "text",     "cx": 1450, "cy": 360, "w": 90,  "h": 16, "text": "noise color"},
    ],

    # ============================================================
    # TONE SCULPT (bottom section, y ≈ 560-780)
    # ============================================================
    "tone_sculpt": [
        {"id": "eqPowerBtn",    "type": "big_btn",  "cx": 85,   "cy": 605, "r": 45},
        {"id": "rainbow_decor", "type": "decor",    "cx": 85,   "cy": 680, "w": 140, "h": 50},
        {"id": "eqCanvas",      "type": "display",  "cx": 745,  "cy": 660, "w": 1130,"h": 200, "color": "black"},
        {"id": "eq_node_1",     "type": "eq_node",  "cx": 225,  "cy": 635, "r": 18},
        {"id": "eq_node_2",     "type": "eq_node",  "cx": 555,  "cy": 635, "r": 18},
        {"id": "eq_node_3",     "type": "eq_node",  "cx": 890,  "cy": 635, "r": 18},
        {"id": "eq_node_4",     "type": "eq_node",  "cx": 1240, "cy": 635, "r": 18},
        {"id": "eq1_freq_lbl",  "type": "text",     "cx": 220,  "cy": 672, "w": 50,  "h": 14, "text": "20Hz"},
        {"id": "eq1_db_lbl",    "type": "text",     "cx": 220,  "cy": 692, "w": 62,  "h": 14, "text": "48dB HP"},
        {"id": "eq2_freq_lbl",  "type": "text",     "cx": 555,  "cy": 672, "w": 54,  "h": 14, "text": "500Hz"},
        {"id": "eq2_db_lbl",    "type": "text",     "cx": 555,  "cy": 692, "w": 48,  "h": 14, "text": "-0.0dB"},
        {"id": "eq3_freq_lbl",  "type": "text",     "cx": 890,  "cy": 672, "w": 38,  "h": 14, "text": "2.0k"},
        {"id": "eq3_db_lbl",    "type": "text",     "cx": 890,  "cy": 692, "w": 48,  "h": 14, "text": "-0.0dB"},
        {"id": "eq4_freq_lbl",  "type": "text",     "cx": 1240, "cy": 672, "w": 48,  "h": 14, "text": "20.0k"},
        {"id": "eq4_db_lbl",    "type": "text",     "cx": 1240, "cy": 692, "w": 62,  "h": 14, "text": "48dB LP"},
        {"id": "complementBtn", "type": "pill",     "cx": 1400, "cy": 570, "w": 115, "h": 28, "text": "COMPLEMENT"},
        {"id": "freqKnob",      "type": "knob",     "cx": 1420, "cy": 615, "r": 28},
        {"id": "freqLabel",     "type": "text",     "cx": 1420, "cy": 655, "w": 50,  "h": 14, "text": "freq"},
        {"id": "gainKnob",      "type": "knob",     "cx": 1420, "cy": 685, "r": 28},
        {"id": "gainLabel",     "type": "text",     "cx": 1420, "cy": 725, "w": 50,  "h": 14, "text": "gain"},
        {"id": "qEqKnob",       "type": "knob",     "cx": 1420, "cy": 755, "r": 22},
        {"id": "qEqLabel",      "type": "text",     "cx": 1420, "cy": 790, "w": 40,  "h": 14, "text": "Q"},
        # EQ axis freq labels on the canvas
        {"id": "eq_ax_100",     "type": "text",     "cx": 470,  "cy": 780, "w": 40,  "h": 14, "text": "100"},
        {"id": "eq_ax_1k",      "type": "text",     "cx": 745,  "cy": 780, "w": 28,  "h": 14, "text": "1k"},
        {"id": "eq_ax_10k",     "type": "text",     "cx": 1020, "cy": 780, "w": 38,  "h": 14, "text": "10k"},
    ],

    # ============================================================
    # KEYBOARD — cosmetic addition in ChatGPT PNG
    # ============================================================
    "keyboard": {
        "x1": 25, "y1": 810, "x2": 1320, "y2": 970,
        "num_white": 14,
        "labels": ["C","D","E","F","G","A","B","C","D","E","F","G","A","B"],
    },
}


def flatten_to_spec(auth=AUTHORITATIVE_ELEMENTS):
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
    groups = ["header", "left_panel", "center_panel", "right_panel", "tone_sculpt"]
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
            elif t in ("pill", "pill_wide", "pill_small", "dropdown", "square_btn",
                       "small_btn", "toggle", "icon", "color_ind", "digital",
                       "vslider", "display", "decor"):
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
    kb = auth.get("keyboard")
    if kb:
        spec["keyboard_strip"] = {"x1": kb["x1"], "y1": kb["y1"], "x2": kb["x2"], "y2": kb["y2"]}
    bc = next((e for g in groups for e in auth.get(g, []) if e.get("id") == "bandCanvas"), None)
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
          f"rects={len(spec['rectangles'])}, texts={len(spec['texts'])}, keyboard={'yes' if spec['keyboard_strip'] else 'no'}")
