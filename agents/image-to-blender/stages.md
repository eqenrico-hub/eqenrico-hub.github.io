# Image-to-Blender Staged Pipeline

This agent advances through **four sequential stages**. Each stage has an
automated **verify** check. The agent does NOT advance until the current
stage passes.

## Stage 1 — Element Presence & Position

**Goal:** every interactive/visual element from the source control list is
represented in the Blender scene at approximately the correct position.

**Inputs:**
- Authoritative element list (hardcoded in `authoritative_elements.py`
  for the target plugin, or derived from the plugin's HTML source file)
- Chassis reference PNG (for visual comparison only)

**Operations:**
1. Load the authoritative list.
2. Apply to Blender via `apply.py`.
3. Run `verify.py --stage=1` — counts, positions, categories.
4. Fix any gaps (missing IDs, misplaced positions, wrong categories).
5. Loop until verify passes.

**Pass criteria:**
- ✅ Every authoritative ID has a corresponding `I2B_*` object in the scene.
- ✅ Each element's bounding box overlaps the expected position within
  a 40px tolerance.
- ✅ No spurious I2B objects that aren't in the authoritative list.

**Do not advance until all three pass.**

---

## Stage 2 — Position Refinement & Colour Sampling

**Goal:** snap each authoritative element's position to the exact pixel
location in the chassis PNG, and sample its dominant color from the PNG.

**Operations:**
1. Run OpenCV detection on the chassis PNG.
2. For each authoritative element, find the nearest matching CV detection
   (circle for knobs, rect for panels) and snap position to its center.
3. Sample the median BGR color under each element's footprint and assign
   it as the element's material base color.
4. Re-apply in Blender with sampled colors.
5. Run `verify.py --stage=2` — diff between authoritative expected centers
   and snapped centers; diff between sampled colors and expected palette.

**Pass criteria:**
- ✅ Every authoritative element has a sampled color (no fallback defaults).
- ✅ Snapped position within 15px of the chassis PNG's visual center for that element.
- ✅ Render-side comparison: with chassis hidden, each element's color matches
  what's at that pixel position in the chassis (within Δ = 20 per channel).

---

## Stage 3 — Decorative Detail

**Goal:** add non-interactive decorative elements present in the chassis
PNG — filigree, frames, dividers, rainbow accents, ornamental glyphs.

**Operations:**
1. Detect decorative contours via color-distinct segmentation excluding
   already-claimed regions.
2. Build flat textured planes or extruded outlines for each.
3. `verify.py --stage=3` — visual similarity score between no-chassis render
   and chassis PNG (SSIM or similar structural metric).

**Pass criteria:**
- ✅ SSIM between no-chassis render and chassis PNG > 0.70

---

## Stage 4 — Text Glyphs

**Goal:** render text labels as actual glyphs (not placeholder planes).

**Operations:**
1. For each `texts` entry in the authoritative spec, create a FONT curve
   with the actual string.
2. Match font, size, color to the chassis PNG's typography.
3. `verify.py --stage=4` — OCR-on-render matches authoritative text labels.

**Pass criteria:**
- ✅ All authoritative text strings OCR-readable in the no-chassis render.

---

## Usage

```bash
# Run the full staged pipeline
python3 runner.py /path/to/chassis.png

# Stop / resume at a given stage
python3 runner.py /path/to/chassis.png --stage=2

# Verify a stage manually
python3 verify.py /path/to/spec.json --stage=1
```

The runner auto-advances only when verify passes.
