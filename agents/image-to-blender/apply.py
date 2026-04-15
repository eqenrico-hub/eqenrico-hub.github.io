"""
Blender-side applier for image-to-blender detection v3.

Reads a JSON spec produced by detect.py v3 and builds 3D geometry for
every detected element using sampled per-element colors so the scene
can stand alone without the chassis PNG underneath.

Usage (in Blender scripting tab or via mcp-blender bridge):
    exec(open('/path/to/apply.py').read())
    apply_spec('/path/to/spec.json', chassis_png='/path/to/chassis.png')  # with chassis
    apply_spec('/path/to/spec.json', chassis_png=None)                    # rebuild only
"""
import bpy, bmesh, math, json
from mathutils import Vector
from pathlib import Path


PX_TO_M = 0.001
COLLECTION_NAME = "ImageToBlender_V2"


def _ensure_collection(name):
    coll = bpy.data.collections.get(name)
    if coll is None:
        coll = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(coll)
    return coll


def _material_from_rgba(name, rgba, rough=0.45, metal=0.0):
    m = bpy.data.materials.get(name)
    if m is None:
        m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    b.inputs["Base Color"].default_value = rgba
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    nt.links.new(b.outputs["BSDF"], out.inputs["Surface"])
    return m


def _infer_metal_rough(rgba):
    """Heuristic: brass/gold colors → metallic. Near-black → dark matte."""
    r, g, b, _ = rgba
    # Warm amber/brass heuristic: high R, moderate G, low B
    if r > 0.5 and g > 0.3 and b < 0.4:
        return 0.8, 0.30
    # Cool metal: near equal RGB and bright
    if abs(r - g) < 0.08 and abs(g - b) < 0.08 and r > 0.55:
        return 0.6, 0.35
    # Otherwise: matte
    return 0.0, 0.55


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
    o = bpy.data.objects.new(name, mesh)
    coll.objects.link(o)
    for p in mesh.polygons:
        p.use_smooth = True
    o.data.materials.append(mat)
    return o


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
    o = bpy.data.objects.new(name, mesh)
    coll.objects.link(o)
    o.data.materials.append(mat)
    return o


def setup_chassis(chassis_png_path, coll):
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
    bm.faces.new([v1, v2, v3, v4])
    uv = bm.loops.layers.uv.new("UVMap")
    for face in bm.faces:
        for loop in face.loops:
            x = (loop.vert.co.x + W/2) / W
            y = (loop.vert.co.y + H/2) / H
            loop[uv].uv = (x, y)
    bm.to_mesh(mesh); bm.free()
    obj = bpy.data.objects.new("I2B_Chassis", mesh)
    coll.objects.link(obj)
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


def apply_spec(json_path, chassis_png=None, clear_old=True):
    with open(json_path) as f:
        spec = json.load(f)
    coll = _ensure_collection(COLLECTION_NAME)
    if chassis_png:
        setup_chassis(chassis_png, coll)
    if clear_old:
        for o in list(bpy.data.objects):
            if o.name.startswith("I2B_") and o.name != "I2B_Chassis":
                bpy.data.objects.remove(o, do_unlink=True)

    # --- Knobs with sampled colors ---
    for i, k in enumerate(spec.get("knobs", [])):
        cx, cy = _px_to_world(spec, k["cx"], k["cy"])
        r = k["r"] * PX_TO_M
        rgba = tuple(k.get("rgba", (0.7, 0.45, 0.18, 1.0)))
        metal, rough = _infer_metal_rough(rgba)
        m_outer = _material_from_rgba(f"I2B_M_Knob_{i:02d}", rgba, rough=rough, metal=metal)
        m_cap = _material_from_rgba(f"I2B_M_KnobCap_{i:02d}",
                                    (rgba[0]*0.25, rgba[1]*0.25, rgba[2]*0.25, 1.0),
                                    rough=0.5, metal=metal*0.7)
        _cylinder(f"I2B_Knob_{i:02d}_outer", cx, cy, r, 0.002, 0.008, m_outer, coll)
        _cylinder(f"I2B_Knob_{i:02d}_cap", cx, cy, max(r*0.55, 0.006), 0.008, 0.011, m_cap, coll)

    # --- Small circles ---
    for i, s in enumerate(spec.get("small_circles", [])):
        cx, cy = _px_to_world(spec, s["cx"], s["cy"])
        r = s["r"] * PX_TO_M
        rgba = tuple(s.get("rgba", (0.95, 0.72, 0.25, 1.0)))
        m = _material_from_rgba(f"I2B_M_Small_{i:02d}", rgba, rough=0.3, metal=0.5)
        _cylinder(f"I2B_Small_{i:02d}", cx, cy, r, 0.007, 0.010, m, coll)

    # --- Rectangles — only build 3D for the truly INTERACTIVE ones ---
    # Let the chassis PNG handle display/decor/dropdown/label flat surfaces.
    INTERACTIVE_RECT_KINDS = {
        "pill", "pill_wide", "pill_small",
        "square_button", "square_btn",
        "vslider", "vertical_slider", "vertical_slider_candidate",
    }
    for i, r in enumerate(spec.get("rectangles", [])):
        if r["kind"] not in INTERACTIVE_RECT_KINDS:
            continue
        x1, y1 = _px_to_world(spec, r["x"], r["y"])
        x2, y2 = _px_to_world(spec, r["x"] + r["w"], r["y"] + r["h"])
        rgba = tuple(r.get("rgba", (0.1, 0.08, 0.08, 1.0)))
        metal, rough = _infer_metal_rough(rgba)
        m = _material_from_rgba(f"I2B_M_Rect_{i:02d}", rgba, rough=rough, metal=metal)
        # Vertical slider: only build the THUMB (a small box in the middle, not the full track)
        if "slider" in r["kind"]:
            cx = (x1 + x2) / 2
            cy = (y1 + y2) / 2
            tw = abs(x2 - x1) * 0.85
            th = abs(y2 - y1) * 0.15
            _box(f"I2B_SliderThumb_{i:02d}", cx - tw/2, cy - th/2, cx + tw/2, cy + th/2,
                 0.004, 0.009, m, coll)
        else:
            _box(f"I2B_Rect_{i:02d}_{r['kind']}", x1, y1, x2, y2, 0.003, 0.007, m, coll)
    # Skip color_regions entirely when chassis PNG is present — it already shows them.
    # Skip spectrum strip — JUCE draws the live visualizer; chassis PNG is the "off" art.

    # --- Keyboard: skip if chassis PNG is present (chassis already shows painted keys) ---
    # Stage 3+ will add subtle 3D edges; for now chassis PNG is authoritative for keyboard appearance.
    kb = spec.get("keyboard_strip")

    # Skip texts when chassis is present — chassis shows them. Stage 4 will render glyphs.

    print(f"Applied: knobs={len(spec.get('knobs', []))}, "
          f"small={len(spec.get('small_circles', []))}, "
          f"rects={len(spec.get('rectangles', []))}, "
          f"color_regions={len(spec.get('color_regions', []))}, "
          f"spectrum={'yes' if spec.get('spectrum_strip') else 'no'}, "
          f"keyboard={'yes' if spec.get('keyboard_strip') else 'no'}, "
          f"texts={len(spec.get('texts', []))}")


def hide_chassis(hidden=True):
    c = bpy.data.objects.get("I2B_Chassis")
    if c:
        c.hide_viewport = hidden
        c.hide_render = hidden


if __name__ == "__main__":
    print("apply.py — use apply_spec(...) / hide_chassis(True) in Blender")
