"""
Autonomous GUI-to-Blender orchestrator with ID-pass pixel-diff feedback loop.

Pipeline:
  1. Flatten authoritative elements → spec JSON
  2. Refine: snap to CV detections + sample colors from chassis PNG
  3. Polish: semantic alignment rules (rows, symmetry, centering)
  4. Auto-align: edge-projection clustering
  5. Apply to Blender + render ID pass (unique color per element)
  6. ID-diff: compare rendered centroids vs spec → exact dx/dy errors
  7. Apply corrections (skip outliers >50px) → loop until avg <3px

Also supports a final Vision scoring pass for subjective quality.

Usage (in Claude Code with Blender MCP):
    The orchestrator is designed to be called step-by-step via MCP.
    Each step produces files in WORK_DIR that feed the next step.

    # Full pipeline:
    python3 orchestrator.py <chassis.png> [--max-iters 5] [--target-error 3]
"""
import json, sys, os, argparse, subprocess, base64
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
WORK_DIR = Path("/Users/ricosan/Downloads")


def run_step(name, cmd):
    print(f"\n{'='*60}")
    print(f"  STAGE: {name}")
    print(f"{'='*60}")
    r = subprocess.run(cmd, capture_output=True, text=True)
    print(r.stdout)
    if r.returncode != 0:
        print(f"  STDERR: {r.stderr}")
        raise RuntimeError(f"Stage '{name}' failed (exit {r.returncode})")
    return r.stdout


# === PIPELINE STAGES ===

def stage1_flatten(out_path):
    run_step("flatten", ["python3", str(SCRIPT_DIR / "authoritative_elements.py"), str(out_path)])


def stage2_refine(spec_path, chassis_png, out_path):
    run_step("refine", [
        "python3", str(SCRIPT_DIR / "refine.py"),
        str(spec_path), str(chassis_png), "--out", str(out_path),
    ])


def stage3_polish(spec_path, out_path):
    run_step("polish", [
        "python3", str(SCRIPT_DIR / "polish.py"),
        str(spec_path), "--out", str(out_path),
    ])


def stage4_align(spec_path, out_path, tolerance=6):
    run_step("auto-align", [
        "python3", str(SCRIPT_DIR / "auto_align.py"),
        str(spec_path), "--out", str(out_path), "--tolerance", str(tolerance),
    ])


def stage5_id_diff(spec_path, id_pass_path, id_colors_path):
    """Run ID-pass diff and return parsed results."""
    from id_diff import id_diff
    return id_diff(str(spec_path), str(id_pass_path), str(id_colors_path))


def stage6_apply_corrections(spec_path, corrections, out_path, max_delta=50):
    """Apply ID-diff corrections, skip outliers."""
    spec = json.load(open(spec_path))
    by_id = {}
    for cat in ("knobs", "small_circles", "rectangles", "texts"):
        for e in spec.get(cat, []):
            if "id" in e:
                by_id[e["id"]] = e

    applied = 0
    for c in corrections:
        eid = c["element_id"]
        field = c["field"]
        current = c["current"]
        suggested = c["suggested"]
        if eid not in by_id or field not in by_id[eid]:
            continue
        if abs(suggested - current) > max_delta:
            continue
        by_id[eid][field] = suggested
        applied += 1
        e = by_id[eid]
        if field == "cx" and "w" in e:
            e["x"] = e["cx"] - e["w"] // 2
        elif field == "cy" and "h" in e:
            e["y"] = e["cy"] - e["h"] // 2

    json.dump(spec, open(str(out_path), "w"), indent=2)
    return applied


# === BLENDER SCRIPT GENERATORS ===

def blender_apply_and_id_render(spec_path, id_pass_path, id_colors_path):
    """Generate Blender Python code for apply + ID-pass render."""
    return f"""
import bpy, json, bmesh, math
from pathlib import Path

# Apply spec
exec(open('{SCRIPT_DIR / "apply.py"}').read())
apply_spec('{spec_path}', chassis_png=None, clear_old=True, mode='full')
hide_chassis(True)

# Load spec for element→color mapping
spec = json.load(open('{spec_path}'))
all_ids = []
for cat in ('knobs', 'small_circles', 'rectangles', 'texts'):
    for e in spec.get(cat, []):
        if 'id' in e:
            all_ids.append(e['id'])

id_colors = {{}}
for i, eid in enumerate(all_ids):
    r = ((i * 37 + 50) % 200 + 30) / 255.0
    g = ((i * 73 + 100) % 200 + 30) / 255.0
    b = ((i * 113 + 150) % 200 + 30) / 255.0
    id_colors[eid] = (r, g, b, 1.0)

# Map objects to IDs
obj_to_id = {{}}
for i, k in enumerate(spec.get('knobs', [])):
    eid = k.get('id', f'knob_{{i}}')
    obj_to_id[f'I2B_Knob_{{i:02d}}_outer'] = eid
    obj_to_id[f'I2B_Knob_{{i:02d}}_cap'] = eid
for i, s in enumerate(spec.get('small_circles', [])):
    eid = s.get('id', f'small_{{i}}')
    obj_to_id[f'I2B_Small_{{i:02d}}'] = eid
for i, r in enumerate(spec.get('rectangles', [])):
    eid = r.get('id', f'rect_{{i}}')
    kind = r.get('kind', 'rect')
    if 'slider' in kind:
        obj_to_id[f'I2B_SliderTrack_{{i:02d}}'] = eid
        obj_to_id[f'I2B_SliderThumb_{{i:02d}}'] = eid
    else:
        obj_to_id[f'I2B_Rect_{{i:02d}}_{{kind}}'] = eid
for i, t in enumerate(spec.get('texts', [])):
    eid = t.get('id', f'text_{{i}}')
    obj_to_id[f'I2B_Text_{{i:02d}}_{{eid}}'] = eid
for i in range(14):
    obj_to_id[f'I2B_WK_{{i:02d}}'] = 'keyboard_white'
for i in range(20):
    obj_to_id[f'I2B_BK_{{i:02d}}'] = 'keyboard_black'
id_colors['keyboard_white'] = (0.95, 0.95, 0.95, 1.0)
id_colors['keyboard_black'] = (0.05, 0.05, 0.05, 1.0)

# Assign unique emission materials
for obj in bpy.data.objects:
    if not obj.name.startswith('I2B_'):
        continue
    eid = obj_to_id.get(obj.name)
    if eid and eid in id_colors:
        mat_name = f'I2B_ID_{{eid}}'
        mat = bpy.data.materials.get(mat_name)
        if mat is None:
            mat = bpy.data.materials.new(mat_name)
            mat.use_nodes = True
            nt = mat.node_tree
            nt.nodes.clear()
            out = nt.nodes.new("ShaderNodeOutputMaterial")
            emit = nt.nodes.new("ShaderNodeEmission")
            emit.inputs["Color"].default_value = id_colors[eid]
            emit.inputs["Strength"].default_value = 1.0
            nt.links.new(emit.outputs["Emission"], out.inputs["Surface"])
        obj.data.materials.clear()
        obj.data.materials.append(mat)

# Camera setup
cam = bpy.data.objects.get("Camera")
if cam is None:
    cam_data = bpy.data.cameras.new("Camera")
    cam = bpy.data.objects.new("Camera", cam_data)
    bpy.context.scene.collection.objects.link(cam)
bpy.context.scene.camera = cam
cam.data.type = 'ORTHO'
cam.location = (0, 0, 2.0)
cam.rotation_euler = (0, 0, 0)
cam.data.ortho_scale = 1619 * 0.001

# Black background, no lights
scene = bpy.context.scene
for obj in list(bpy.data.objects):
    if obj.type == 'LIGHT':
        bpy.data.objects.remove(obj, do_unlink=True)
if scene.world and scene.world.use_nodes:
    bg = scene.world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs["Color"].default_value = (0.0, 0.0, 0.0, 1.0)
        bg.inputs["Strength"].default_value = 1.0

# Raw color (no sRGB gamma)
scene.view_settings.view_transform = 'Raw'
scene.render.engine = 'CYCLES'
scene.cycles.samples = 32
scene.render.resolution_x = 1619
scene.render.resolution_y = 971
scene.render.filepath = '{id_pass_path}'
bpy.ops.render.render(write_still=True)

json.dump(id_colors, open('{id_colors_path}', 'w'), indent=2)
print("ID_PASS_DONE")
"""


def blender_final_render(spec_path, render_path):
    """Generate Blender code for final pretty render."""
    return f"""
import bpy, math

exec(open('{SCRIPT_DIR / "apply.py"}').read())
apply_spec('{spec_path}', chassis_png=None, clear_old=True, mode='full')
hide_chassis(True)

# Camera
cam = bpy.data.objects.get("Camera")
if cam is None:
    cam_data = bpy.data.cameras.new("Camera")
    cam = bpy.data.objects.new("Camera", cam_data)
    bpy.context.scene.collection.objects.link(cam)
bpy.context.scene.camera = cam
cam.data.type = 'ORTHO'
cam.location = (0, 0, 2.0)
cam.rotation_euler = (0, 0, 0)
cam.data.ortho_scale = 1619 * 0.001

# Lighting
scene = bpy.context.scene
for obj in list(bpy.data.objects):
    if obj.type == 'LIGHT':
        bpy.data.objects.remove(obj, do_unlink=True)

light_data = bpy.data.lights.new("FlatSun", type='SUN')
light_data.energy = 3.0
light_data.angle = math.radians(60)
light_obj = bpy.data.objects.new("FlatSun", light_data)
bpy.context.scene.collection.objects.link(light_obj)
light_obj.location = (0, 0, 3)
light_obj.rotation_euler = (0, 0, 0)

if scene.world and scene.world.use_nodes:
    bg = scene.world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs["Color"].default_value = (0.12, 0.10, 0.10, 1.0)
        bg.inputs["Strength"].default_value = 0.3

scene.view_settings.view_transform = 'Standard'
scene.render.engine = 'CYCLES'
scene.cycles.samples = 64
scene.render.resolution_x = 1619
scene.render.resolution_y = 971
scene.render.filepath = '{render_path}'
bpy.ops.render.render(write_still=True)
print("FINAL_RENDER_DONE")
"""


# === MAIN ORCHESTRATOR ===

def run_pipeline(chassis_png, max_iters=5, target_error=3.0):
    """Full pipeline. Returns dict with final status."""
    chassis_png = str(Path(chassis_png).resolve())

    print(f"\n{'#'*60}")
    print(f"  AUTONOMOUS GUI-TO-BLENDER PIPELINE")
    print(f"  Chassis: {chassis_png}")
    print(f"  Max iterations: {max_iters}")
    print(f"  Target avg error: {target_error}px")
    print(f"{'#'*60}")

    # Stage 1-4: prep pipeline (runs outside Blender)
    s1 = WORK_DIR / "pipe_s1_auth.json"
    s2 = WORK_DIR / "pipe_s2_refined.json"
    s3 = WORK_DIR / "pipe_s3_polished.json"
    s4 = WORK_DIR / "pipe_s4_aligned.json"

    stage1_flatten(s1)
    stage2_refine(s1, chassis_png, s2)
    stage3_polish(s2, s3)
    stage4_align(s3, s4)

    current_spec = s4
    best_error = float("inf")
    best_spec = current_spec

    for iteration in range(1, max_iters + 1):
        print(f"\n{'*'*60}")
        print(f"  ITERATION {iteration}/{max_iters}")
        print(f"{'*'*60}")

        # Stage 5: Render ID pass in Blender
        id_pass = WORK_DIR / f"pipe_idpass_i{iteration}.png"
        id_colors = WORK_DIR / f"pipe_idcolors_i{iteration}.json"
        blender_code = blender_apply_and_id_render(current_spec, id_pass, id_colors)

        # Save blender script for MCP execution
        script_path = WORK_DIR / f"_blender_idpass_i{iteration}.py"
        script_path.write_text(blender_code)
        print(f"\n  Blender script: {script_path}")
        print(f"  Execute via MCP: exec(open('{script_path}').read())")
        print(f"  Then resume: python3 orchestrator.py --resume {iteration} {chassis_png}")

        # Save state
        state = {
            "iteration": iteration,
            "max_iters": max_iters,
            "target_error": target_error,
            "chassis_png": chassis_png,
            "current_spec": str(current_spec),
            "id_pass": str(id_pass),
            "id_colors": str(id_colors),
            "best_error": best_error,
            "best_spec": str(best_spec),
        }
        json.dump(state, open(str(WORK_DIR / "pipe_state.json"), "w"), indent=2)
        return {"status": "waiting_for_blender", "script": str(script_path)}


def resume_after_idpass(chassis_png):
    """Resume after Blender rendered the ID pass."""
    state = json.load(open(str(WORK_DIR / "pipe_state.json")))
    iteration = state["iteration"]
    max_iters = state["max_iters"]
    target_error = state["target_error"]
    current_spec = Path(state["current_spec"])
    id_pass = Path(state["id_pass"])
    id_colors = Path(state["id_colors"])
    best_error = state.get("best_error", float("inf"))
    best_spec = Path(state.get("best_spec", current_spec))

    if not id_pass.exists():
        return {"status": "error", "message": f"ID pass not found: {id_pass}"}

    # Stage 6: ID-diff scoring
    sys.path.insert(0, str(SCRIPT_DIR))
    from id_diff import id_diff
    result = id_diff(str(current_spec), str(id_pass), str(id_colors))
    s = result["summary"]

    print(f"\n  ITERATION {iteration} SCORE:")
    print(f"    Found: {s['found']}/{s['total']}")
    print(f"    Avg error: {s['avg_error_px']}px (target: {target_error}px)")
    print(f"    Under 2px: {s['under_2px']}, under 5px: {s['under_5px']}")

    if s["avg_error_px"] < best_error:
        best_error = s["avg_error_px"]
        best_spec = current_spec

    # Check pass condition
    if s["avg_error_px"] <= target_error:
        print(f"\n  PASS — avg error {s['avg_error_px']}px <= {target_error}px")
        # Generate final pretty render script
        final_render = WORK_DIR / "pipe_final_render.png"
        script = WORK_DIR / "_blender_final.py"
        script.write_text(blender_final_render(best_spec, final_render))
        return {
            "status": "pass",
            "avg_error": s["avg_error_px"],
            "iteration": iteration,
            "final_spec": str(best_spec),
            "final_render_script": str(script),
        }

    if iteration >= max_iters:
        print(f"\n  MAX ITERS — best avg error: {best_error}px")
        final_render = WORK_DIR / "pipe_final_render.png"
        script = WORK_DIR / "_blender_final.py"
        script.write_text(blender_final_render(best_spec, final_render))
        return {
            "status": "max_iterations",
            "avg_error": best_error,
            "iteration": iteration,
            "final_spec": str(best_spec),
            "final_render_script": str(script),
        }

    # Apply corrections
    corrected = WORK_DIR / f"pipe_corrected_i{iteration}.json"
    applied = stage6_apply_corrections(
        current_spec, result["corrections"], corrected, max_delta=50
    )
    print(f"  Applied {applied} corrections")

    # Next iteration: re-polish + re-align
    next_polished = WORK_DIR / f"pipe_polished_i{iteration + 1}.json"
    next_aligned = WORK_DIR / f"pipe_aligned_i{iteration + 1}.json"
    stage3_polish(corrected, next_polished)
    stage4_align(next_polished, next_aligned, tolerance=max(3, 6 - iteration))

    # Recurse
    next_state = {
        "iteration": iteration + 1,
        "max_iters": max_iters,
        "target_error": target_error,
        "chassis_png": chassis_png,
        "current_spec": str(next_aligned),
        "id_pass": str(WORK_DIR / f"pipe_idpass_i{iteration + 1}.png"),
        "id_colors": str(WORK_DIR / f"pipe_idcolors_i{iteration + 1}.json"),
        "best_error": best_error,
        "best_spec": str(best_spec),
    }
    json.dump(next_state, open(str(WORK_DIR / "pipe_state.json"), "w"), indent=2)

    # Generate next ID-pass script
    script = WORK_DIR / f"_blender_idpass_i{iteration + 1}.py"
    script.write_text(blender_apply_and_id_render(
        next_aligned,
        next_state["id_pass"],
        next_state["id_colors"],
    ))
    print(f"\n  Next Blender script: {script}")
    return {
        "status": "needs_next_iteration",
        "avg_error": s["avg_error_px"],
        "iteration": iteration,
        "corrections_applied": applied,
        "next_script": str(script),
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("chassis")
    p.add_argument("--max-iters", type=int, default=5)
    p.add_argument("--target-error", type=float, default=3.0)
    p.add_argument("--resume", action="store_true")
    args = p.parse_args()

    if args.resume:
        result = resume_after_idpass(args.chassis)
    else:
        result = run_pipeline(args.chassis, args.max_iters, args.target_error)

    print(f"\nResult: {json.dumps(result, indent=2)}")
