# Band Ritual 3D — Methodology Log

**Goal**: build a photorealistic 3D Blender model of the Band Ritual VST plugin GUI
starting from an AI-redesigned PNG + a hand-traced shape JSON, pixel-perfect aligned
and interactively texturable.

This doc tracks every problem → solution so we can later **compile a complete agent**
that automates the whole flow.

---

## Inputs

- **Reference PNG**: `/Users/ricosan/eqenrico-hub.github.io/agents/gui-frame-tool/gemini_reference.png` (1619×971, AI-redesigned Band Ritual Final 1)
- **Traced JSON**: `/Users/ricosan/Downloads/shapes.json` — 46 shapes (23 rect + 22 circle + 1 frame)
- **Frame constants**: `x=7.334, y=7.334, w=1604.33, h=957.10` — biggest rect in JSON = chassis boundary
- **Blender scene**: top-down ortho camera, chassis 0.813 × 0.485 m

---

## Phase 1 — 3D scaffolding from JSON

**Problem**: build the chassis + one 3D primitive per traced shape, positioned pixel-perfect.

**Solution**:
1. Biggest rect in JSON = **frame** = chassis boundary. Chassis = extruded cube scaled to frame aspect (1.676).
2. **Pixel → Blender conversion** (frame-relative):
   ```python
   pct_x = (px - FRAME_X) / FRAME_W
   pct_y = (py - FRAME_Y) / FRAME_H
   blender_x = (pct_x - 0.5) * CHASSIS_W
   blender_y = (0.5 - pct_y) * CHASSIS_H   # Y flip: image Y↓ → world Y↑
   radius   = (pr / FRAME_W) * CHASSIS_W
   ```
3. **Element → primitive** (no interpretation, literal one-to-one):
   - `circle` → 4-piece knob: skirt (torus) + body (cylinder + bevel + subsurf) + dome (half UV sphere) + indicator (extruded cube)
   - `rect` → recessed cube (depth into chassis)
   - `ring` → flattened torus
   - `arc` / `polygon` → bmesh extrusion

**Key rule learned**: never decide "this circle is a knob and that circle is a toggle button" — shape type is the geometry type, semantic classification is a separate pass.

---

## Phase 2 — Coordinate validation (alignment bug)

**Problem**: the ON/OFF button 3D knob appeared ~90 px above its actual position in the PNG (visible gap between the 3D knob and the pink ON/OFF button on the chassis texture underneath).

**Diagnosis path**:
1. Verified JSON math was internally consistent (Blender object sizes = expected Blender sizes from JSON).
2. **Hand-traced JSON was imprecise**: user traced id=30 at cy=704 in `shapes.json` but the actual PNG pink power button was at cy≈765–865 (found by PIL pixel color scan for dark-magenta cluster).
3. Manually moved knob id=30 to corrected cy=865 → visually matched.

**Solution (agent-level)**: new **`frame-to-blender-aligner`** agent at `eqenrico-hub/agents/frame-to-blender-aligner/`:
- `refine_shapes.py` — CV refinement pass: Hough circles (±30% radius) + Canny-edge projections (±15% rect side) to snap rough traces to actual PNG features. Bounded, cannot invent new shapes.
- `build_blender.py` — scene builder: shadeless Emission chassis + 4-piece knobs + recessed rects.
- `validate.py` — per-shape alignment score, flags mismatches < 0.6 for re-refinement.

---

## Phase 3 — Materials (solid → extracted → per-position projection)

**Problem**: solid-colored 3D elements look nothing like the photorealistic PNG. User said "non sembrano realistici per nulla".

**Iteration log**:

1. **Attempt 1 — solid colors** (Principled BSDF dark purple + metallic). Looks like plastic, not plugin. ❌
2. **Attempt 2 — extract texture patches from PNG, apply to all same-type elements** (one knob texture for all 22 knobs, one rect texture for all 23 rects). Simple and fast. But user observed:
   > "top bar rects are brown wood, chord/scale rects are whitish, display is black" — **using ONE rect texture is wrong**.
3. **Attempt 3 — shared world-space UV material** (each rect samples PNG at its own world position via Geometry.Position shader). Good direction but **Y-flip bug**: `v = -y/CHASSIS_H + 0.5` (wrong) instead of `v = y/CHASSIS_H + 0.5` (right). Caused mirrored text on some elements.
4. **Attempt 4 — per-rect independent materials with editable Mapping offset**. Each rect = own material. Initial offset = rect's own PNG area. User can DRAG the offset interactively (Phase 4).

**Key shader structure** (per rect):
```
Geometry.Position → SeparateXYZ
  → X / CHASSIS_W + 0.5 → UV.x
  → Y / CHASSIS_H + 0.5 → UV.y     (NO Y flip!)
  → CombineXYZ → Mapping (Scale = FRAME/PNG, Location = frame offset + drag offset)
  → Image Texture (reference PNG) → Emission → Output
```

**Chassis material**: pure `Emission` shader (shadeless). PNG displays exactly as the file — no environment tinting, no specular shift.

**Key rules learned**:
- Rendering aspect ratio must match frame aspect (1604.33 / 957.10) or the keyboard strip gets cropped at top/bottom.
- Camera must be strictly top-down ortho, `location = (0, 0, 1)`, `rotation = (0, 0, 0)`, `ortho_scale = CHASSIS_W`.
- Camera can drift (observed `location.y = -0.084` after manual interaction). Always reset before rendering.

---

## Phase 4 — Interactive texture control

**Problem**: user wants to pick/adjust textures without re-running Python every time.

**Iteration log**:

1. **Separate webapp `texture-previewer`** — dropped (user said "keep it in the existing tool, don't load anything extra").
2. **Integrated into GUI Frame Tool** (`agents/gui-frame-tool/index.html`):
   - New sidebar `Texture` section between "Selected shape" and "All shapes".
   - **Shift-click multi-select** on canvas + shape list.
   - Texture library built dynamically from loaded PNG + traced shapes:
     - `OWN AREA` — default, sample from shape's own PNG position.
     - `from_shape_N` — one entry per traced shape, lets you reuse shape N's pixels as texture for any other shape.
     - Alt-drag on stage defines a custom rectangular patch from any PNG area.
   - Each shape can store a `texture_id`. Export JSON includes `texture_library` (custom patches) + per-shape `texture_id`.
   - **PNG-agnostic** — no hardcoded coordinates, works with any PNG the user loads.
3. **Blender-side interactive drag**: modal operator `br.drag_rect_texture`, keybind `T`:
   - Select a rect → press T → mouse movement scrolls the PNG window behind the rect.
   - Press **X** = lock horizontal axis only, **Y** = lock vertical only.
   - **Enter / click** = commit, **Esc / right-click** = revert.
   - Header bar shows live offset X/Y.
   - Also exposed as a button in N-panel > Item tab > "Band Ritual — Texture Drag".

4. **N-panel controls (no-modal path)** — primary UI because modal mode can conflict with Blender's native S/scroll shortcuts:
   - **PAN**: click-drag `X offset` / `Y offset` sliders — move the PNG window behind the rect. Rect geometry never changes size.
   - **ZOOM**: click-drag `X zoom` / `Y zoom` sliders — lower = texture appears bigger in the rect (showing a smaller PNG area), higher = smaller texture. **Lock X=Y zoom** button keeps proportions.

5c. **Attaching the reference image causes detail-scale distortion** (discovered 2026-04-18, late session):
   - When the user attached the first approved texture PNG to subsequent minimal prompts ("same texture, different size"), Gemini treated it as image-to-image: stretched the source's scratches, rust marks and grain to fill the new wider canvas, producing unnaturally enlarged details that don't match the original density.
   - **Fix**: do NOT attach the reference image on subsequent prompts. Rely on the chat's memory of the originally generated texture — Gemini will sample from its stylistic memory and produce a fresh texture at the new aspect with details at the right scale.
   - If drift still appears, add one line to the prompt:
     ```
     Keep scratch/rust marks at the same ABSOLUTE pixel size as the first texture
     — do not stretch or scale details. Add more marks at the same density instead.
     ```
   - **Rule for the agent**: emit text-only prompts for the batch. Only the seed (initial) prompt may reference-attach an image. Every follow-up must be text-only to prevent density drift.

5b. **Verbose prompts cause style drift — use minimal prompts** (discovered 2026-04-18):
   - First iteration: prompt described the target texture style (palette, grain, rust, bezel, etc.) in detail. Gemini drifted into adding heavy chrome frames with explicit screws (Image #27) — technically correct per the prompt, but visually different from the first texture the user approved.
   - Second iteration: minimal prompt — `"Same texture as before, sized W × H pixels (aspect ratio X:1, keep this ratio exactly — do not distort)."`. Gemini replied with a texture consistent with the first one because the chat context already carried the style. User: "PERFETTO HA FUNZIONATO BENISSIMO STAVOLTA".
   - **Rule**: once the LLM has produced ONE approved reference texture in a chat, **every subsequent prompt must reference it by memory, not re-describe it**. New prompt = only size + aspect + "same as before". Any descriptive word added to the new prompt risks drift.
   - For the future agent: emit prompts with this minimal format only, plus a single one-shot seed prompt at the start of the session to establish the style. Never re-seed mid-session.

6a. **Batch prompt generation per unique aspect ratio**:
   - N rects → group by rounded aspect → K unique aspects (K ≤ N). Only K prompts needed because rects with the same aspect share a texture.
   - For 23 Band Ritual rects: 21 unique aspects (one aspect — 1.92:1 — is shared by 3 rects).
   - Prompts are ordered by group size desc, then by aspect asc. User downloads PNGs in the SAME ORDER, then the agent matches them back by creation time → group → auto-crop-per-rect → apply.
   - Output the prompt file in a plain `.txt` the user can paste one-by-one into an LLM chat.

5a. **AI image generators ignore exact pixel dimensions** (discovered 2026-04-18):
   - Asked Gemini for `1024 × 180 px` (aspect 5.68:1), got `2672 × 400 px` (aspect 6.68:1) — 17% aspect error.
   - Root cause: Imagen/Gemini/DALL-E generate at their model's native resolutions with a small set of aspect presets (1:1, 16:9, 9:16, 4:3, 3:4, sometimes ultra-wide). Arbitrary dimensions are treated as hints, not hard requirements.
   - Fix: **auto-crop on load**. When the user loads a custom PNG in Blender, the `br.load_rect_texture` operator now detects the aspect mismatch and center-crops the PNG symmetrically to match the rect's aspect before feeding it to the Image Texture node. Prevents interior distortion even when the LLM disobeys the requested size.
   - Rule for the agent: **never trust an LLM's pixel-size compliance**. Always post-process the returned image to match the target aspect.

5. **Aspect-ratio preservation for LLM-generated textures** (added 2026-04-18, after fit distortion):
   - Issue: clicking "Fit texture to rect" stretches a square-ish ChatGPT image onto an extremely wide rect (e.g. 5.68:1), distorting the interior while keeping nice borders.
   - Fix: the N-panel now shows, per selected rect:
     - native pixel size in the source PNG (e.g. `233 × 41 px`),
     - exact aspect ratio (`5.683:1`),
     - suggested ChatGPT canvas size (`1024 × 180 px`).
   - **Copy ChatGPT prompt** button writes a ready-made prompt to the clipboard, pre-filled with the correct dimensions + "no text, no labels, style-matches-reference" guidance.
   - Rule: always ask the LLM for a canvas that matches the target rect's aspect ratio. No downstream distortion, no stretched interiors.

6. **Custom per-rect texture from a Gemini-generated clean PNG** (new workflow added 2026-04-18):
   - **When to use**: the world-space projection of the original PNG onto a rect produces a noisy/blurred look because the area on the PNG has text labels, chassis grain, or compression artifacts at that exact position. You want a **clean, isolated texture** that matches the Band Ritual style but without the surrounding noise.
   - **Process**:
     1. Take a screenshot of the specific GUI section whose texture you want to reuse (e.g. the chord/scale dropdown area).
     2. Feed the screenshot to **Gemini** (or any vision-capable LLM) with a prompt like *"generate me a clean seamless texture in this exact style, no labels, no artifacts, same color palette and surface grain"*.
     3. Save the Gemini-returned image as a PNG on disk.
     4. In Blender: select the target rect → N-panel > Texture Drag > **Load custom PNG…** → pick the Gemini-generated PNG.
     5. Operator `br.load_rect_texture` swaps the Image Texture node's image and resets Mapping Scale=1, Location=0 so the new PNG fills the rect exactly.
     6. Per-rect custom property `custom_texture_path` is set so the N-panel can display the current source and the `Revert to original PNG` button can roll back to world-space sampling of the main reference PNG.
   - **Why this matters for the agent**: texture quality is the last 10% of photoreal. CV-sampled pixels from the original PNG carry noise; an LLM-generated clean texture derived from a small reference patch gives a cleaner final look while staying on-style.

---

## Rules collected (will shape the future agent)

1. **Biggest rect in JSON = chassis frame**. Every position is frame-relative.
2. **No semantic interpretation at build time**. `circle` → knob, `rect` → panel, period.
3. **CV refinement is bounded** — it tightens, never invents.
4. **Chassis = shadeless Emission**. Photoreal knob sides come from Principled BSDF + HDRI, but the chassis texture itself must render 1:1.
5. **UV math matches chassis cube projection**: `V = y/CHASSIS_H + 0.5` (no flip).
6. **Render aspect = frame aspect** (else keyboard crops).
7. **Camera drifts**. Always reset `location = (0, 0, 1)` + `rotation = 0` + `ortho_scale = CHASSIS_W` before final render.
8. **Each rect gets its own material** so per-element offset is independent.
9. **Texture library is PNG-agnostic** — built from the image + traced shapes at runtime.
10. **Destructive changes** (bulk delete, reset position, overwriting) must be confirmed before running — user already lost hours to a premature `rm -rf`.
11. **When the original PNG's local area is too noisy to use as a texture**, screenshot-that-section → feed-to-Gemini → get a clean in-style texture → load on the rect via N-panel "Load custom PNG". This is the texture-quality escape hatch.
12. **Texture reuse across rects**: once a Gemini texture works on one rect, `Copy this texture` + `Paste to selected` / `Apply to ALL rects` propagates it. Each target rect re-crops the SAME source PNG to its OWN aspect ratio before fitting — no distortion, no per-rect Gemini call.
13. **Blender's embedded Python has NO PIL**. Anything that needs image manipulation (crop, resize, compose) must shell out via `subprocess` to system `python3`. Already baked into `auto_crop_to_aspect_system()`.

---

## Current state (as of this log entry)

- **Blender scene**: complete — 1 chassis + 23 rect + 22 circle (2 of which are ring-sized with bezel pieces, giga + 21 small knobs). All positions pixel-perfect per refined JSON.
- **Materials**: chassis shadeless Emission, rects per-rect world-mapped with draggable Mapping offset, knobs 4-piece with extracted texture patches (knob_top, giga_knob).
- **Textures saved**: `/Users/ricosan/Desktop/br_textures/` (knob_top.png, giga_knob.png, knob_skirt.png, display_panel.png, rect_panel.png).
- **Render aspect**: 1619 × 965 (matches frame aspect 1.677).
- **GUI Frame Tool**: texture panel + multi-select + Alt-drag live on GitHub Pages.
- **Blender interactive drag**: T keybind + N-panel button live in the current session.

---

## Phase 5 — 9-slice / center-crop texture batch application (breakthrough)

**Problem**: 21 per-aspect Gemini prompts worked but had two issues — (a) every prompt produced a slightly different border style, (b) LLM image-to-image stretched detail marks (scratches, rust spots) to fit new canvases, so small wide rects showed oversized marks.

**Final solution** (user's idea, refined):

1. **ONE master material texture** from an LLM. Center material only — no borders, no frame. 1024×1024 or larger. Example approved: 1254×1254 chassis material PNG from ChatGPT.
2. **Per-rect center-crop** at correct aspect (`nine_slice_band_ritual.py` on Desktop — the script handles 9-slice with crop-only + optional tile, no stretching anywhere). For center-only textures like the 1254×1254 we used, pure aspect-crop from the source center is sufficient — no 9-slice needed.
3. **Bevel modifier on each rect** (0.5mm, angle-limited) to produce **3D-geometry borders**. Borders catch light naturally from scene lighting — no baked borders in textures. Consistent across all 23 rects, scales perfectly to any size.

**Outcome** (user verdict): "this is perfect. It looks amazing."

**Key insight**: let the TEXTURE carry only the material (grain, color, patina) and let the 3D GEOMETRY carry the borders (bevel modifier). This separation is the clean architectural move — textures stay simple and reusable, geometry is where the "button-ness" lives.

---

## Rules added in Phase 5

14. **Separate concerns: textures = material, geometry = borders.** LLM generates a single borderless material; Blender's bevel modifier produces 3D border shading at render time. Scales to any rect count without per-rect texture variation.
15. **When an LLM produces a single good material PNG, prefer center-crop-to-rect-aspect over per-rect LLM generation.** It eliminates variation between rects and guarantees identical look.
16. **Bevel modifier on top-face cube rects**: `width = 0.0005` (0.5mm), `segments = 3`, `limit_method = 'ANGLE'`, `angle_limit = 30°`. Tested at this scale, holds up for all 23 rects from the smallest button well to the keyboard strip.

---

## Phase 6 — In-Blender texture paint on the chassis PNG

**Problem**: after deleting a 3D element (e.g., Shape_16_circle), the chassis PNG still shows the original art of that element underneath. User wanted to clone-stamp the unwanted area with clean chassis pixels, directly in Blender (Photoshop-style clone brush).

**Failed attempts**:
1. **OpenCV inpaint** (auto content-aware fill). Too blurry for the fine chassis grain — user: "terrible".
2. **Texture Paint mode with the original `Generated + Mapping` material**. Paint strokes landed in the wrong pixels because the Mapping node transformed UVs between mesh and image. Clicking spot A painted at pixel B.
3. **Texture Paint with `UV` output instead of `Generated`**. All 6 cube faces had UVs covering 0-1 (from `cube_project`), so the image tiled on every face — sides showed stripes of piano keys, colours bled everywhere.

**Working solution** (Phase 6 final):

```python
# 1. Re-UV the chassis with bmesh:
#    - Top face → planar UV 0→1 mapped to mesh XY bounds
#    - All other faces → UV collapsed to (0, 0) (no texture visible there)
for face in bm.faces:
    if face.normal.z > 0.9:
        for loop in face.loops:
            u = (loop.vert.co.x - bbox_min_x) / w
            v = (loop.vert.co.y - bbox_min_y) / h
            loop[uv_layer].uv = (u, v)
    else:
        for loop in face.loops:
            loop[uv_layer].uv = (0.0, 0.0)

# 2. Pre-crop the reference PNG to just the frame area (so no Mapping node needed):
#    Image becomes exactly the paintable canvas, 1604×957 instead of 1619×971.

# 3. Material: TexCoord.UV → Image Texture → Emission. No Mapping node.
#    The UV input is now clean 1:1 with the image pixels for the top face.

# 4. Enter Texture Paint mode, select Clone brush, set clone_image + canvas to the cropped PNG.
```

Now Ctrl+click sets the clone source at the exact pixel under the cursor, click-drag paints pixel-perfect on the chassis top face. Works like Photoshop's clone stamp.

**Rules added in Phase 6**:

17. **Texture Paint requires UV output, not Generated.** `Generated` is per-vertex procedural — Blender's paint brush cannot invert it to know which pixel to modify.
18. **Cube-projected UVs break texture paint on a cube chassis** because all 6 faces share UV 0-1. Either collapse non-top UVs to (0,0), or use a plane instead of a cube for the chassis.
19. **If the material has a Mapping node between UV and Image, paint strokes drift by the Mapping transform.** Pre-crop the PNG on disk instead of cropping via Mapping, so the shader is UV → Image directly with no transform.
20. **Don't paint on the original reference PNG.** Work on a separate paintable copy (`bandritual_chassis_paintable.png`) so the original is preserved as a backup.

---

## Next steps

- [ ] Finalize texture assignment for every rect using the T-key drag flow (or GUI Frame Tool → export JSON → Blender reads `texture_id`).
- [ ] Decide knob treatment: keep extracted texture patches or switch to per-knob world-mapped sampling.
- [ ] Add subtle shadows / ambient occlusion between chassis and knobs for depth without going photoreal-plastic.
- [ ] Export final render at full resolution.
- [ ] **Compile this methodology into a new agent** (provisional name: `vst-gui-to-blender-pipeline` or fold into existing `frame-to-blender-aligner` as an extension). Agent responsibilities:
  1. Refine JSON trace with CV.
  2. Build Blender scene with chassis + primitives + materials.
  3. Apply texture assignments from GUI Frame Tool JSON.
  4. Validate alignment, flag mismatches.
  5. Expose the interactive drag operator for manual texture tuning.
  6. Render at correct aspect.
  7. Support per-rect texture overrides with user-supplied PNGs (screenshot→Gemini→clean-texture path).

---

*Log will grow as we keep iterating. Keep this file open when we continue the session.*
