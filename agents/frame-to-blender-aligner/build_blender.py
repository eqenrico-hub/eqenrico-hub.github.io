"""
Frame-to-Blender Aligner — Scene Builder

Reads a refined shape JSON and a reference PNG, builds a Blender scene
with chassis-textured base and a 3D primitive per shape, positioned at
frame-relative coordinates. Designed to be executed inside Blender
(via `blender --python build_blender.py -- refined.json reference.png`
or the Blender MCP `execute_blender_code` bridge).

Coordinate system:
    Biggest rect in JSON = FRAME of the GUI (chassis boundary).
    Every other shape = pixel coordinates on the full PNG.
    px → Blender conversion expressed as fraction of FRAME × chassis size.
    Chassis is UV-cube-projected, texture UV-cropped to the frame area
    so shapes and artwork align pixel-perfect.

Element → primitive map:
    circle   → 4-piece knob (skirt + body + dome + indicator)
    rect     → recessed panel (dark material, beveled)
    ring     → flat torus (bezel)
    arc      → extruded arc segment (bmesh)
    polygon  → extruded polygon (bmesh)

Intentionally NO interpretation of what each shape "means" — it is the
user's traced geometry, period.
"""

import bpy
import bmesh
import json
import math
import sys
from PIL import Image


def parse_args():
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    if len(argv) < 2:
        raise SystemExit("Usage: build_blender.py -- refined.json reference.png [chassis_w=0.813]")
    return {
        "json": argv[0],
        "png":  argv[1],
        "chassis_w": float(argv[2]) if len(argv) > 2 else 0.813,
    }


def build(json_path, png_path, chassis_w=0.813):
    data = json.load(open(json_path))
    shapes = data["shapes"]

    # Frame = biggest rect
    frame = max((s for s in shapes if s["type"] == "rect"),
                key=lambda s: s["w"] * s["h"])
    FX, FY, FW, FH = frame["x"], frame["y"], frame["w"], frame["h"]

    # PNG dimensions
    png = Image.open(png_path)
    PW, PH = png.size

    chassis_h = chassis_w * (FH / FW)
    Z_TOP = 0.01

    def px_to_xy(px, py):
        return ((px - FX) / FW - 0.5) * chassis_w, (0.5 - (py - FY) / FH) * chassis_h

    def px_to_r(pr):
        return (pr / FW) * chassis_w

    # Clear scene
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)

    # Chassis: cube scaled to frame aspect, textured
    bpy.ops.mesh.primitive_cube_add(size=1.0)
    chassis = bpy.context.object
    chassis.name = "Chassis"
    chassis.scale = (chassis_w, chassis_h, 0.008)
    bpy.ops.object.transform_apply(scale=True)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.uv.cube_project(cube_size=1.0)
    bpy.ops.object.mode_set(mode='OBJECT')

    # Emission material (shadeless — texture displays as-is)
    mat = bpy.data.materials.new("Chassis_Tex")
    mat.use_nodes = True
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mapping = nt.nodes.new("ShaderNodeMapping")
    mapping.inputs["Scale"].default_value = (FW / PW, FH / PH, 1.0)
    mapping.inputs["Location"].default_value = (FX / PW, (PH - FY - FH) / PH, 0.0)
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(png_path, check_existing=True)
    emit = nt.nodes.new("ShaderNodeEmission")
    out  = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(tc.outputs["Generated"], mapping.inputs["Vector"])
    nt.links.new(mapping.outputs["Vector"], tex.inputs["Vector"])
    nt.links.new(tex.outputs["Color"], emit.inputs["Color"])
    nt.links.new(emit.outputs["Emission"], out.inputs["Surface"])
    chassis.data.materials.append(mat)

    # Materials for shapes
    def material(name, color, metallic=0.0, roughness=0.5, emission=0.0):
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        b = m.node_tree.nodes["Principled BSDF"]
        b.inputs["Base Color"].default_value = (*color, 1.0)
        b.inputs["Metallic"].default_value = metallic
        b.inputs["Roughness"].default_value = roughness
        if emission > 0:
            b.inputs["Emission Color"].default_value = (*color, 1.0)
            b.inputs["Emission Strength"].default_value = emission
        return m

    mat_skirt = material("KN_Skirt", (0.55, 0.50, 0.60), 1.0, 0.22)
    mat_body  = material("KN_Body",  (0.06, 0.03, 0.10), 0.0, 0.35)
    mat_top   = material("KN_Top",   (0.09, 0.04, 0.14), 0.0, 0.30)
    mat_ind   = material("KN_Ind",   (1.0, 0.95, 1.0), emission=4.5)
    mat_rect  = material("Panel",    (0.04, 0.02, 0.06), 0.0, 0.85)
    mat_ring  = material("Ring",     (0.4, 0.3, 0.5), 1.0, 0.25)

    collection = bpy.data.collections.new("Shapes")
    bpy.context.scene.collection.children.link(collection)

    for s in shapes:
        sid = s["id"]
        if s is frame:
            continue
        t = s["type"]

        if t == "circle":
            x, y = px_to_xy(s["cx"], s["cy"])
            r = px_to_r(s["r"])
            _build_knob(collection, sid, x, y, r, Z_TOP, mat_skirt, mat_body, mat_top, mat_ind)

        elif t == "rect":
            cx = s["x"] + s["w"] / 2
            cy = s["y"] + s["h"] / 2
            x, y = px_to_xy(cx, cy)
            bw, bh = px_to_r(s["w"]) * (FW / FW), (s["h"] / FH) * chassis_h
            _build_rect(collection, sid, x, y, bw, bh, Z_TOP, mat_rect)

        elif t == "ring":
            x, y = px_to_xy(s["cx"], s["cy"])
            ro = px_to_r(s["r_out"])
            ri = px_to_r(s["r_in"])
            _build_ring(collection, sid, x, y, ro, ri, Z_TOP, mat_ring)

        elif t == "arc":
            x, y = px_to_xy(s["cx"], s["cy"])
            ro = px_to_r(s.get("r_out", s.get("r", 20)))
            ri = px_to_r(s.get("r_in", s.get("r", 20) * 0.7))
            a0 = math.radians(s.get("start_angle", 0))
            a1 = math.radians(s.get("end_angle", 270))
            _build_arc(collection, sid, x, y, ro, ri, a0, a1, Z_TOP, mat_ring)

        elif t == "polygon":
            pts = [px_to_xy(p[0], p[1]) for p in s["points"]]
            _build_polygon(collection, sid, pts, Z_TOP, mat_rect)

    # Ortho top-down camera
    bpy.ops.object.camera_add(location=(0, 0, 1.0))
    cam = bpy.context.object
    cam.data.type = 'ORTHO'
    cam.data.ortho_scale = chassis_w
    cam.rotation_euler = (0, 0, 0)
    bpy.context.scene.camera = cam

    print(f"Built {len(shapes) - 1} shapes + chassis on {chassis_w} × {chassis_h} m")


def _link(collection, obj):
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    collection.objects.link(obj)


def _build_knob(col, sid, x, y, r, z_top, mat_skirt, mat_body, mat_top, mat_ind):
    skirt_h = 0.003
    body_h = 0.010
    body_r = r * 0.92
    top_r = body_r * 0.95
    top_z = z_top + skirt_h + body_h
    dome_peak = top_z + top_r * 0.22
    ind_h = 0.0015

    bpy.ops.mesh.primitive_cylinder_add(radius=r * 1.02, depth=skirt_h,
                                        location=(x, y, z_top + skirt_h/2), vertices=48)
    skirt = bpy.context.object
    skirt.name = f"Shape_{sid}_circle_skirt"
    skirt.data.materials.append(mat_skirt)
    bpy.ops.object.shade_smooth()
    _link(col, skirt)

    bpy.ops.mesh.primitive_cylinder_add(radius=body_r, depth=body_h,
                                        location=(x, y, z_top + skirt_h + body_h/2), vertices=48)
    body = bpy.context.object
    body.name = f"Shape_{sid}_circle"
    body.data.materials.append(mat_body)
    bev = body.modifiers.new("Bevel", 'BEVEL')
    bev.width = body_h * 0.35
    bev.segments = 4
    bev.limit_method = 'ANGLE'
    bev.angle_limit = math.radians(30)
    bpy.ops.object.shade_smooth()
    _link(col, body)

    bpy.ops.mesh.primitive_uv_sphere_add(radius=top_r, location=(x, y, top_z),
                                         segments=48, ring_count=24)
    top = bpy.context.object
    top.scale.z = 0.22
    bpy.ops.object.transform_apply(scale=True)
    bm = bmesh.new()
    bm.from_mesh(top.data)
    to_remove = [v for v in bm.verts if v.co.z < top_z - 1e-5]
    bmesh.ops.delete(bm, geom=to_remove, context='VERTS')
    bm.to_mesh(top.data)
    bm.free()
    top.name = f"Shape_{sid}_circle_top"
    top.data.materials.append(mat_top)
    bpy.ops.object.shade_smooth()
    _link(col, top)

    bpy.ops.mesh.primitive_cube_add(size=1.0,
                                    location=(x, y + r * 0.35, dome_peak + ind_h))
    ind = bpy.context.object
    ind.scale = (r * 0.07, r * 0.45, ind_h)
    bpy.ops.object.transform_apply(scale=True)
    ind.name = f"Shape_{sid}_circle_ind"
    ind.data.materials.append(mat_ind)
    _link(col, ind)


def _build_rect(col, sid, x, y, bw, bh, z_top, mat):
    depth = 0.003
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(x, y, z_top - depth/2))
    obj = bpy.context.object
    obj.scale = (bw, bh, depth)
    bpy.ops.object.transform_apply(scale=True)
    obj.name = f"Shape_{sid}_rect"
    obj.data.materials.append(mat)
    _link(col, obj)


def _build_ring(col, sid, x, y, r_out, r_in, z_top, mat):
    h = 0.008
    bpy.ops.mesh.primitive_torus_add(
        major_radius=(r_out + r_in) / 2,
        minor_radius=(r_out - r_in) / 2,
        location=(x, y, z_top + h/2),
        major_segments=48, minor_segments=12,
    )
    obj = bpy.context.object
    obj.scale.z = 0.3
    bpy.ops.object.transform_apply(scale=True)
    obj.name = f"Shape_{sid}_ring"
    obj.data.materials.append(mat)
    _link(col, obj)


def _build_arc(col, sid, x, y, r_out, r_in, a0, a1, z_top, mat):
    depth = 0.004
    if a1 < a0:
        a1 += 2 * math.pi
    bm = bmesh.new()
    segs = 32
    vo, vi = [], []
    for i in range(segs + 1):
        t = i / segs
        ang = a0 + (a1 - a0) * t
        vo.append(bm.verts.new((math.cos(ang) * r_out, math.sin(ang) * r_out, 0)))
        vi.append(bm.verts.new((math.cos(ang) * r_in,  math.sin(ang) * r_in,  0)))
    for i in range(segs):
        try:
            bm.faces.new([vo[i], vo[i+1], vi[i+1], vi[i]])
        except ValueError:
            pass
    ext = bmesh.ops.extrude_face_region(bm, geom=bm.faces[:])
    for v in [v for v in ext["geom"] if isinstance(v, bmesh.types.BMVert)]:
        v.co.z += depth
    mesh = bpy.data.meshes.new(f"Shape_{sid}_arc_mesh")
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(f"Shape_{sid}_arc", mesh)
    obj.location = (x, y, z_top)
    bpy.context.scene.collection.objects.link(obj)
    obj.data.materials.append(mat)
    _link(col, obj)


def _build_polygon(col, sid, pts, z_top, mat):
    depth = 0.004
    cx = sum(p[0] for p in pts) / len(pts)
    cy = sum(p[1] for p in pts) / len(pts)
    bm = bmesh.new()
    verts = [bm.verts.new((p[0] - cx, p[1] - cy, 0)) for p in pts]
    try:
        bm.faces.new(verts)
    except ValueError:
        pass
    ext = bmesh.ops.extrude_face_region(bm, geom=bm.faces[:])
    for v in [v for v in ext["geom"] if isinstance(v, bmesh.types.BMVert)]:
        v.co.z += depth
    mesh = bpy.data.meshes.new(f"Shape_{sid}_poly_mesh")
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(f"Shape_{sid}_polygon", mesh)
    obj.location = (cx, cy, z_top)
    bpy.context.scene.collection.objects.link(obj)
    obj.data.materials.append(mat)
    _link(col, obj)


if __name__ == "__main__":
    args = parse_args()
    build(args["json"], args["png"], args["chassis_w"])
