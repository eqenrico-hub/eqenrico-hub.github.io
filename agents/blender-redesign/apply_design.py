"""
Paste a ChatGPT-style element table into this file (TABLE variable below)
then run in Blender. It rebuilds the section geometry to match.

Origin convention: input is (X, Y, W, H) in mm, origin top-left of the section.
Blender is centered-Y-up. This script does the conversion.
"""
import bpy, bmesh
from mathutils import Vector

# ---- 1. Paste ChatGPT's table here (# | Name | Type | X | Y | W | H | Notes) ----
TABLE = """
1 | KEY            | dropdown | 4   | 6   | 40  | 12 |
2 | SCALE TYPE     | dropdown | 48  | 6   | 60  | 12 |
3 | SCALE AMOUNT   | slider   | 160 | 4   | 14  | 40 |
4 | CHORD DEGREE   | dropdown | 4   | 22  | 35  | 12 |
5 | CHORD TYPE     | dropdown | 43  | 22  | 35  | 12 |
6 | CHORD AMOUNT   | slider   | 140 | 4   | 14  | 40 |
7 | TUNING         | button   | 4   | 40  | 150 | 8  |
"""

SECTION_ROOT_NAME = 'ScaleChordBox'   # existing object whose bbox anchors the section
# ---------------------------------------------------------------------------------

def bbox(o):
    mw = o.matrix_world
    bb = [mw @ Vector(c) for c in o.bound_box]
    return min(v.x for v in bb), max(v.x for v in bb), min(v.y for v in bb), max(v.y for v in bb)

def parse(table):
    rows = []
    for line in table.strip().splitlines():
        parts = [p.strip() for p in line.split('|')]
        if len(parts) < 7 or not parts[0].isdigit(): continue
        rows.append({
            'num': int(parts[0]), 'name': parts[1], 'type': parts[2],
            'x': float(parts[3]), 'y': float(parts[4]),
            'w': float(parts[5]), 'h': float(parts[6]),
            'notes': parts[7] if len(parts) > 7 else ''
        })
    return rows

root = bpy.data.objects[SECTION_ROOT_NAME]
sx1, sx2, sy1, sy2 = bbox(root)
SEC_W = (sx2 - sx1) * 1000  # mm
SEC_H = (sy2 - sy1) * 1000
print(f"Section world: {SEC_W:.1f}×{SEC_H:.1f}mm at X[{sx1:.3f},{sx2:.3f}] Y[{sy1:.3f},{sy2:.3f}]")

def mm_to_world(mx, my, mw, mh):
    # Input: mm, origin top-left of section, Y+ down
    # Output: world Blender coords (x1, x2, y1, y2) with Y+ up
    wx1 = sx1 + mx / 1000
    wx2 = wx1 + mw / 1000
    wy2 = sy2 - my / 1000          # top-left Y maps to sy2 - my
    wy1 = wy2 - mh / 1000
    return wx1, wx2, wy1, wy2

M_BTN   = bpy.data.materials.get('M_Button')
M_BEZ   = bpy.data.materials.get('M_Bezel')
M_PANEL = bpy.data.materials.get('M_PanelDark')
M_LABEL = bpy.data.materials.get('M_Label')

def make_panel(name, x1, x2, y1, y2, mat=M_BTN, z_top=0.006, z_bot=0.003, bevel=0.35, segs=8):
    old = bpy.data.objects.get(name)
    if old: bpy.data.objects.remove(old, do_unlink=True)
    mesh = bpy.data.meshes.new(name); bm = bmesh.new()
    v = [bm.verts.new((x,y,z)) for z in (z_bot,z_top) for y in (y1,y2) for x in (x1,x2)]
    for f in [(0,1,3,2),(4,6,7,5),(0,2,6,4),(1,5,7,3),(0,4,5,1),(2,3,7,6)]:
        bm.faces.new([v[i] for i in f])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh); bm.free()
    o = bpy.data.objects.new(name, mesh); bpy.context.collection.objects.link(o)
    if mat: o.data.materials.append(mat)
    b = o.modifiers.new('Bevel','BEVEL')
    b.width = (y2-y1) * bevel
    b.segments = segs
    b.limit_method = 'ANGLE'
    b.profile = 0.7
    for p in o.data.polygons: p.use_smooth = True
    return o

rows = parse(TABLE)
print(f"Applying {len(rows)} elements…")
for r in rows:
    x1, x2, y1, y2 = mm_to_world(r['x'], r['y'], r['w'], r['h'])
    name = r['name'].strip().replace(' ', '')
    t = r['type'].lower()
    mat = M_PANEL if 'slider' in t else M_BTN
    make_panel(f'Redesign_{name}', x1, x2, y1, y2, mat=mat)
    print(f"  {r['num']}: {r['name']} ({t}) → Blender X[{x1:.3f},{x2:.3f}] Y[{y1:.3f},{y2:.3f}]")
print("Done.")
