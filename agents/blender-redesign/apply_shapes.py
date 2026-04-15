"""
Reads shapes_export.json (from shape-design HTML page) and builds 3D extruded
rings in Blender matching the exported outlines.

Each shape becomes a Bezier-style polygonal mesh ring:
- Outer outline = exported polygon vertices (gear, rosette, polygon, circle, etc.)
- Inner outline = circle (cutout) so it's a true ring
- Extruded between z_bot and z_top with bevel modifier for premium edges
- Stacked at decreasing Z height (outer ring lowest, inner ring highest)

Workflow:
  1. In browser shapes.html, design shapes
  2. Click 'Export shapes JSON' → downloads shapes_export.json
  3. Move to /Users/ricosan/Downloads/shapes_export.json
  4. Run this script in Blender (paste into Scripting tab or via mcp-blender bridge)
"""
import bpy, bmesh, json, math
from pathlib import Path
from mathutils import Vector

JSON_PATH = '/Users/ricosan/Downloads/shapes_export.json'
SECTION_CENTER_OBJ = 'ScaleKnob_Depression'  # use existing depression for placement
SCALE_PX_TO_M = 0.0667 / 540   # convert: outer-most radius 540 px ≈ 66.7mm world

def bbox(o):
    mw = o.matrix_world
    bb = [mw @ Vector(c) for c in o.bound_box]
    return min(v.x for v in bb), max(v.x for v in bb), min(v.y for v in bb), max(v.y for v in bb)

dep = bbox(bpy.data.objects[SECTION_CENTER_OBJ])
WORLD_CX = (dep[0]+dep[1]) / 2
WORLD_CY = (dep[2]+dep[3]) / 2
print(f"Knob world center: ({WORLD_CX:.4f}, {WORLD_CY:.4f})")
print(f"Pixel→meter scale: {SCALE_PX_TO_M:.6f}")

with open(JSON_PATH) as f:
    data = json.load(f)

# Z heights — outer ring lowest, inner ring highest (stacked)
NUM_LAYERS = len(data['shapes'])
Z_BASE = 0.003
Z_STEP = 0.001  # 1mm per stack level
Z_THICK = 0.005

def make_ring_mesh(name, outer_pts_world, inner_pts_world, z_bot, z_top, mat=None):
    """Build a 3D ring mesh between an outer polygon and an inner polygon."""
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()
    # Bottom outer + inner verts
    v_obot = [bm.verts.new((p[0], p[1], z_bot)) for p in outer_pts_world]
    v_otop = [bm.verts.new((p[0], p[1], z_top)) for p in outer_pts_world]
    v_ibot = [bm.verts.new((p[0], p[1], z_bot)) for p in inner_pts_world]
    v_itop = [bm.verts.new((p[0], p[1], z_top)) for p in inner_pts_world]

    nO = len(outer_pts_world)
    nI = len(inner_pts_world)

    # Outer wall (bot → top, around N segments)
    for i in range(nO):
        j = (i+1) % nO
        bm.faces.new([v_obot[i], v_otop[i], v_otop[j], v_obot[j]])
    # Inner wall (top → bot, reversed direction)
    for i in range(nI):
        j = (i+1) % nI
        bm.faces.new([v_itop[j], v_itop[i], v_ibot[i], v_ibot[j]])
    # Top cap — use bridge between outer top loop and inner top loop
    # If nO == nI we can do it directly; else use ngon approach (triangulate later)
    bmesh.ops.bridge_loops(bm, edges=
        [bm.edges.new((v_otop[i], v_otop[(i+1)%nO])) for i in range(nO)] +
        [bm.edges.new((v_itop[i], v_itop[(i+1)%nI])) for i in range(nI)]
    )
    # Bottom cap
    bmesh.ops.bridge_loops(bm, edges=
        [bm.edges.new((v_obot[i], v_obot[(i+1)%nO])) for i in range(nO)] +
        [bm.edges.new((v_ibot[i], v_ibot[(i+1)%nI])) for i in range(nI)]
    )
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    for p in mesh.polygons: p.use_smooth = True
    if mat: obj.data.materials.append(mat)
    # Bevel modifier for premium edge feel
    bv = obj.modifiers.new('Bevel','BEVEL')
    bv.width = 0.0006
    bv.segments = 3
    bv.limit_method = 'ANGLE'
    return obj

# Convert pixel points to world meters, centered on the knob
def px_to_world(p):
    return (WORLD_CX + p[0] * SCALE_PX_TO_M, WORLD_CY + p[1] * SCALE_PX_TO_M)

# Delete existing rings if present
for name in ['ScaleKnob_OuterRing','ScaleKnob_DegreeRing','ScaleKnob_TypeRing']:
    o = bpy.data.objects.get(name)
    if o: bpy.data.objects.remove(o, do_unlink=True)

# Build each shape
SHAPE_TO_BLENDER_NAME = {
    'CHORD_TYPE':   'ScaleKnob_TypeRing',
    'CHORD_DEGREE': 'ScaleKnob_DegreeRing',
    'SCALE_TYPE':   'ScaleKnob_OuterRing',
    'KEY':          'ScaleKnob_InnerDial',  # center disc, no cutout
}

for s in data['shapes']:
    name = SHAPE_TO_BLENDER_NAME.get(s['name'], s['name'])
    layer = s.get('layer_z', 0)
    z_bot = Z_BASE + layer * Z_STEP
    z_top = z_bot + Z_THICK
    outer_world = [px_to_world(p) for p in s['outline_outer_px']]
    if s.get('outline_inner_px'):
        inner_world = [px_to_world(p) for p in s['outline_inner_px']]
        old = bpy.data.objects.get(name)
        if old: bpy.data.objects.remove(old, do_unlink=True)
        make_ring_mesh(name, outer_world, inner_world, z_bot, z_top)
    else:
        # KEY = solid disc (no inner cutout)
        # Just keep existing inner dial; or create a new disc
        pass
    print(f"Built {name} from {s['name']} ({s['kind']}, {len(outer_world)} verts)")

print("Done — refresh viewport, switch to Rendered shading.")
