"""
Blender script: render a tight top-down view of one GUI section with numbered
yellow badges on every interactive element, then write a matching pixel-coordinate
JSON for the overlay compositor.

Usage (inside Blender, via the mcp-blender bridge or a text-editor script):
    # 1. Edit SECTION_ROOT and ELEMENTS below for the section you want to export
    # 2. Run this file
    # 3. Run overlay_numbers.py afterwards to burn the numbered badges into the PNG
"""
import bpy, json
from mathutils import Vector

# ---- CONFIGURE PER SECTION ----
SECTION_ROOT = 'ScaleChordBox'          # object whose bbox defines the framing
ELEMENTS = [                            # (object_name, label_for_prompt)
    ('Dropdown_Key',        'KEY'),
    ('Dropdown_ScaleType',  'SCALE TYPE'),
    ('Slider_Row1',         'SCALE AMOUNT'),
    ('Dropdown_ChordDegree','CHORD DEGREE'),
    ('Dropdown_ChordType',  'CHORD TYPE'),
    ('Slider_Row2',         'CHORD AMOUNT'),
    ('Btn_Tuning',          'TUNING'),
]
OUT_PNG  = '/Users/ricosan/Downloads/section_render.png'
OUT_JSON = '/tmp/section_overlay.json'
MARGIN = 0.008
RENDER_W = 1400
# -------------------------------

def bbox(o):
    mw = o.matrix_world
    bb = [mw @ Vector(c) for c in o.bound_box]
    return min(v.x for v in bb), max(v.x for v in bb), min(v.y for v in bb), max(v.y for v in bb)

root = bpy.data.objects[SECTION_ROOT]
sx1, sx2, sy1, sy2 = bbox(root)

cam = bpy.data.objects.get('Camera')
if cam is None:
    cd = bpy.data.cameras.new('Camera')
    cam = bpy.data.objects.new('Camera', cd)
    bpy.context.collection.objects.link(cam)
bpy.context.scene.camera = cam
cam.data.type = 'ORTHO'

cx = (sx1 + sx2)/2; cy = (sy1 + sy2)/2
w  = (sx2 - sx1) + 2*MARGIN
h  = (sy2 - sy1) + 2*MARGIN
cam.data.ortho_scale = max(w, h)
cam.location = (cx, cy, 0.4)
cam.rotation_euler = (0, 0, 0)

scene = bpy.context.scene
scene.render.engine = 'BLENDER_WORKBENCH'
scene.display.shading.color_type = 'MATERIAL'
H_res = int(RENDER_W * (h/w))
scene.render.resolution_x = RENDER_W
scene.render.resolution_y = H_res
scene.render.image_settings.file_format = 'PNG'
scene.render.filepath = OUT_PNG
bpy.ops.render.render(write_still=True)

# Pixel-coord mapping for overlay step
frame_world_w = cam.data.ortho_scale
frame_world_h = cam.data.ortho_scale * H_res / RENDER_W
x0 = cx - frame_world_w/2
y0 = cy - frame_world_h/2

out = {'image': OUT_PNG, 'width': RENDER_W, 'height': H_res, 'section': SECTION_ROOT, 'elements': []}
for i, (name, label) in enumerate(ELEMENTS, 1):
    o = bpy.data.objects.get(name)
    if not o: continue
    ex1, ex2, ey1, ey2 = bbox(o)
    out['elements'].append({
        'num': i, 'name': name, 'label': label,
        'x1': (ex1-x0)/frame_world_w*RENDER_W,
        'x2': (ex2-x0)/frame_world_w*RENDER_W,
        'y1': H_res - ((ey1-y0)/frame_world_h*H_res),
        'y2': H_res - ((ey2-y0)/frame_world_h*H_res),
    })

with open(OUT_JSON, 'w') as f: json.dump(out, f, indent=2)
print(f"Rendered {OUT_PNG} ({RENDER_W}×{H_res}), {len(out['elements'])} elements → {OUT_JSON}")
