# Frame-to-Blender Aligner

Refines imprecise GUI Frame Tool traces with CV, then builds a pixel-aligned
3D Blender scene using the refined coordinates.

## Why this exists

Hand-traced GUI Frame Tool JSON can be off by tens of pixels
(observed: the ON/OFF button trace was ~90 px above its actual PNG
position). Running that imprecise JSON directly into Blender produces
3D geometry that visibly does not line up with the underlying artwork.

This agent closes that gap with a CV refinement pass plus a render-based
validator, so every element ends up where the PNG says it is.

## Pipeline

```
shapes.json (rough trace)                  reference.png
          |                                       |
          v                                       |
   [refine_shapes.py]  <---------- same PNG ------+
          |
          v
   refined.json  ----- [build_blender.py] -----> Blender scene
                                  |
                                  v
                          render.png  --> [validate.py]  --> alignment_report.json
```

### 1. `refine_shapes.py`

Takes the GUI Frame Tool JSON and the reference PNG, and for each shape
corrects `(cx, cy, r)` or `(x, y, w, h)` using OpenCV:
- **Circles** — Hough circles bounded to ±30% of the traced radius,
  scored by distance to the traced center.
- **Rects** — Canny edges + horizontal/vertical projections, snapping
  each boundary to the strongest edge line within ±15% of the traced
  side.
- **Rings** — double Hough (outer refines, inner scales proportionally).

### 2. `build_blender.py`

Runs inside Blender. Reads refined JSON + PNG, detects the biggest
rect as the GUI frame, sets up a chassis mesh scaled to frame aspect,
UV-crops the PNG to the frame area (the PNG often has a few px of
padding around the real GUI boundary), then emits one 3D primitive per
shape:

| Shape type | Geometry |
|---|---|
| `circle` | 4-piece knob: metallic skirt + matte body (bevelled) + dome top + emissive indicator |
| `rect` | recessed dark panel |
| `ring` | flattened torus bezel |
| `arc` | extruded arc segment (bmesh) |
| `polygon` | extruded polygon (bmesh) |

Chassis uses an `Emission` shader so the PNG texture renders exactly as
it looks in the file — no environment tinting or specular shift. Knobs
use Principled BSDF with metallic + bevel + subdivision for photoreal
reflections.

### 3. `validate.py`

Renders top-down ortho from Blender, compares render vs reference PNG
per shape, writes `alignment_report.json` flagging any shape with an
alignment score below 0.6. This is the "did it actually match?" step
that saves you a manual eyeball pass.

## Usage

```bash
# Step 1 — refine the rough trace
python3 refine_shapes.py shapes.json gemini_reference.png refined.json

# Step 2 — build the Blender scene
# Option A: from the command line
blender --background --python build_blender.py -- refined.json gemini_reference.png
# Option B: paste into the Blender MCP bridge (execute_blender_code)

# Step 3 — validate after rendering
python3 validate.py refined.json gemini_reference.png render.png report.json
```

## Design decisions

**No element semantics.** The shapes are your traced geometry, not an
interpretation. The agent never decides "this circle is a knob and
that one is an on/off button" — every `circle` becomes a 4-piece knob,
every `rect` becomes a recessed panel. Semantic reclassification is a
separate pass (see sibling `image-to-blender` agent).

**Frame-relative coordinates.** The biggest rect in JSON is taken as
the chassis boundary. All positions are `(px - FRAME_X) / FRAME_W`
fractions, so the same JSON works at any chassis render size.

**CV refines, doesn't replace.** Refinement is bounded (±30% radius,
±15% rect side). If CV finds nothing convincing the traced value is
kept. So the agent cannot invent new elements — it only tightens
positions the user already traced.

## Slot in the pipeline

```
Moodboard → VST GUI Pipeline (ChatGPT PNG) → GUI Frame Tool (trace)
    → Frame-to-Blender Aligner  ← you are here
    → Blender Redesign (final polish + render)
```

The sibling agent `image-to-blender` goes the other way: it skips the
manual trace and detects elements automatically. Use Frame-to-Blender
Aligner when the autodetector misses decorations or dropdown slots the
user traced by hand.
