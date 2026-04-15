"""
Blender-side applier for image-to-blender element detection.

Reads a JSON spec produced by detect.py and builds 3D geometry inside
a dedicated Blender collection ON TOP of the source chassis PNG (which
should be added as an image-plane first — see setup_chassis() helper).

Usage (in Blender scripting tab or via mcp-blender bridge):
    exec(open('/path/to/apply.py').read())
    apply_spec('/path/to/detect_spec.json', chassis_png='/path/to/chassis.png')
"""
import bpy, bmesh, math, json
from mathutils import Vector
from pathlib import Path


# ================================================================
# Config — tune for your image/scene
# ================================================================
PX_TO_M = 0.001                # 1 px = 1 mm
COLLECTION_NAME = "ImageToBlender_V2"

MATERIALS = {
    "knob_outer":  {"rgba": (0.70, 0.45, 0.18, 1.0), "rough": 0.35, "metal": 0.85},
    "knob_cap":    {"rgba": (0.18, 0.14, 0.11, 1.0), "rough": 0.45, "metal": 0.60},
    "slider":      {"rgba": (0.85, 0.65, 0.35, 1.0), "rough": 0.30, "metal": 0.80},
    "button_red":  {"rgba": (0.75, 0.18, 0.20, 1.0), "rough": 0.40, "metal": 0.30},
    "button_dark": {"rgba": (0.10, 0.08, 0.08, 1.0), "rough": 0.55, "metal": 0.20},
    "piano_white": {"rgba": (0.92, 0.89, 0.82, 1.0), "rough": 0.45, "metal": 0.00},
    "piano_black": {"rgba": (0.08, 0.07, 0.05, 1.0), "rough": 0.55, "metal": 0.00},
    "eq_node":     {"rgba": (0.95, 0.72, 0.25, 1.0), "rough": 0.25, "metal": 0.70},
}


# ================================================================
# Helpers
# ================================================================
def _ensure_collection(name):
    coll = bpy.data.collections.get(name)
    if coll is None:
        coll = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(coll)
    return coll

def _material(mat_key):
    cfg = MATERIALS[mat_key]
    name = f"M_I2B_{mat_key}"
    m = bpy.data.materials.get(name)
    if m is None:
        m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    b.inputs["Base Color"].default_value = cfg["rgba"]
    b.inputs["Roughness"].default_value = cfg["rough"]
    b.inputs["Metallic"].default_value = cfg["metal"]
    nt.links.new(b.outputs["BSDF"], out.inputs["Surface"])
    return m

def _px_to_world(spec, px, py):
    W = spec["width"] * PX_TO_M
    H = spec["height"] * PX_TO_M
    return (px * PX_TO_M - W / 2, H / 2 - py * PX_TO_M)

def _cylinder(name, cx, cy, r, z_bot, z_top, mat, coll, segs=48):
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()
    tv, bv = [], []
    for i in range(segs):
        a = 2 * math.pi * i / segs
        x, y = cx + math.cos(a) * r, cy + math.sin(a) * r
        tv.append(bm.verts.new((x, y, z_top)))
        bv.append(bm.verts.new((x, y, z_bot)))
    tc = bm.verts.new((cx, cy, z_top))
    bc = bm.verts.new((cx, cy, z_bot))
    for i in range(segs):
        j = (i + 1) % segs
        bm.faces.new([tc, tv[i], tv[j]])
        bm.faces.new([bc, bv[j], bv[i]])
        bm.faces.new([tv[i], bv[i], bv[j], tv[j]])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    coll.objects.link(obj)
    for p in mesh.polygons:
        p.use_smooth = True
    obj.data.materials.append(mat)
    return obj

def _box(name, x1, y1, x2, y2, z_bot, z_top, mat, coll):
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()
    xlo, xhi = min(x1, x2), max(x1, x2)
    ylo, yhi = min(y1, y2), max(y1, y2)
    v = [bm.verts.new((x, y, z)) for z in (z_bot, z_top) for y in (ylo, yhi) for x in (xlo, xhi)]
    for f in [(0, 1, 3, 2), (4, 6, 7, 5), (0, 2, 6, 4), (1, 5, 7, 3), (0, 4, 5, 1), (2, 3, 7, 6)]:
        bm.faces.new([v[i] for i in f])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    coll.objects.link(obj)
    obj.data.materials.append(mat)
    for p in mesh.polygons:
        p.use_smooth = True
    return obj


# ================================================================
# Public API
# ================================================================
def setup_chassis(chassis_png_path: str, coll_name: str = COLLECTION_NAME):
    """Creates an image-plane at z=0 with the chassis PNG as emission texture."""
    import bmesh
    coll = _ensure_collection(coll_name)
    # Remove any existing chassis
    for o in list(bpy.data.objects):
        if o.name.startswith("I2B_Chassis"):
            bpy.data.objects.remove(o, do_unlink=True)
    img = bpy.data.images.load(chassis_png_path, check_existing=True)
    img.colorspace_settings.name = "sRGB"
    W = img.size[0] * PX_TO_M
    H = img.size[1] * PX_TO_M
    mesh = bpy.data.meshes.new("I2B_Chassis")
    bm = bmesh.new()
    v1 = bm.verts.new((-W/2, -H/2, 0))
    v2 = bm.verts.new((+W/2, -H/2, 0))
    v3 = bm.verts.new((+W/2, +H/2, 0))
    v4 = bm.verts.new((-W/2, +H/2, 0))
    f = bm.faces.new([v1, v2, v3, v4])
    uv = bm.loops.layers.uv.new("UVMap")
    for face in bm.faces:
        for loop in face.loops:
            x = (loop.vert.co.x + W/2) / W
            y = (loop.vert.co.y + H/2) / H
            loop[uv].uv = (x, y)
    bm.to_mesh(mesh); bm.free()
    obj = bpy.data.objects.new("I2B_Chassis", mesh)
    coll.objects.link(obj)
    # Material: emission with the PNG
    mat = bpy.data.materials.new("I2B_M_Chassis")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    emit = nt.nodes.new("ShaderNodeEmission")
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    nt.links.new(tex.outputs["Color"], emit.inputs["Color"])
    nt.links.new(emit.outputs["Emission"], out.inputs["Surface"])
    obj.data.materials.append(mat)
    return obj


def apply_spec(json_path: str, chassis_png: str | None = None, clear_old: bool = True):
    """Build 3D elements in Blender from a detect.py JSON spec."""
    with open(json_path) as f:
        spec = json.load(f)
    coll = _ensure_collection(COLLECTION_NAME)
    if chassis_png:
        setup_chassis(chassis_png, COLLECTION_NAME)
    # Remove old I2B elements (except chassis)
    if clear_old:
        for o in list(bpy.data.objects):
            if o.name.startswith("I2B_") and o.name != "I2B_Chassis":
                bpy.data.objects.remove(o, do_unlink=True)

    M_KNOB = _material("knob_outer")
    M_CAP  = _material("knob_cap")
    M_NODE = _material("eq_node")
    M_SLD  = _material("slider")
    M_BTN_DARK = _material("button_dark")
    M_WK   = _material("piano_white")
    M_BK   = _material("piano_black")

    # --- Knobs ---
    for i, k in enumerate(spec.get("knobs", [])):
        cx, cy = _px_to_world(spec, k["cx"], k["cy"])
        r = k["r"] * PX_TO_M
        _cylinder(f"I2B_Knob_{i:02d}_outer", cx, cy, r, 0.002, 0.007, M_KNOB, coll)
        _cylinder(f"I2B_Knob_{i:02d}_cap", cx, cy, max(r*0.55, 0.006), 0.007, 0.010, M_CAP, coll)

    # --- Small circles (EQ nodes) ---
    for i, s in enumerate(spec.get("small_circles", [])):
        cx, cy = _px_to_world(spec, s["cx"], s["cy"])
        r = s["r"] * PX_TO_M
        _cylinder(f"I2B_Node_{i:02d}", cx, cy, r, 0.006, 0.009, M_NODE, coll)

    # --- Rectangles ---
    for i, r in enumerate(spec.get("rectangles", [])):
        x1, y1 = _px_to_world(spec, r["x"], r["y"])
        x2, y2 = _px_to_world(spec, r["x"] + r["w"], r["y"] + r["h"])
        mat = {"vertical_slider_candidate": M_SLD,
               "horizontal_button_candidate": M_BTN_DARK,
               "square_button_candidate": M_BTN_DARK}[r["kind"]]
        _box(f"I2B_Rect_{i:02d}_{r['kind'][:3]}", x1, y1, x2, y2, 0.003, 0.007, mat, coll)

    # --- Keyboard: build white + black keys based on strip bounds ---
    kb = spec.get("keyboard_strip")
    if kb:
        x1w, y1w = _px_to_world(spec, kb["x1"], kb["y1"])
        x2w, y2w = _px_to_world(spec, kb["x2"], kb["y2"])
        total_w = abs(x2w - x1w)
        # Assume 14 white keys (standard vocoder range); tuneable
        num_white = 14
        white_w = total_w / num_white
        gap = 0.0005
        for k in range(num_white):
            kx1 = x1w + k * white_w + gap
            kx2 = x1w + (k + 1) * white_w - gap
            _box(f"I2B_WK_{k:02d}", kx1, y1w, kx2, y2w, 0.001, 0.007, M_WK, coll)
        # Black keys: standard pattern (after C,D,F,G,A within each octave)
        black_after = [0,1,3,4,5, 7,8,10,11,12]
        bh = abs(y2w - y1w) * 0.62
        bk_top_y = y1w  # remember y1w is upper in world space (y flipped)
        # In world coords, y1w corresponds to the TOP of the keyboard zone (smallest py)
        # Actually px_to_world flips y so higher py → lower y_world. Let's recompute cleanly:
        ylo, yhi = min(y1w, y2w), max(y1w, y2w)
        black_top = yhi
        black_bot = yhi - bh
        bw = white_w * 0.58
        for idx, w_after in enumerate(black_after):
            if w_after >= num_white - 1: continue
            boundary = x1w + (w_after + 1) * white_w
            _box(f"I2B_BK_{idx:02d}", boundary - bw/2, black_bot, boundary + bw/2, black_top,
                 0.007, 0.012, M_BK, coll)

    print(f"Applied: {len(spec['knobs'])} knobs, {len(spec['small_circles'])} nodes, "
          f"{len(spec['rectangles'])} rects, keyboard={'yes' if kb else 'no'}")


if __name__ == "__main__":
    print("apply.py — call apply_spec('/path/to/spec.json', chassis_png='/path/to/chassis.png') in Blender")
