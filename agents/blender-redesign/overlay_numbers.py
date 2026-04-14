"""Burn numbered yellow badges into the PNG rendered by render_section.py."""
import json
from PIL import Image, ImageDraw, ImageFont

import sys, glob
# Take explicit path arg, OR find the most recent /tmp/*_overlay.json
if len(sys.argv) > 1:
    JSON_PATH = sys.argv[1]
else:
    candidates = sorted(glob.glob('/tmp/*_overlay.json'), key=lambda p: -__import__('os').path.getmtime(p))
    if not candidates:
        print("No /tmp/*_overlay.json found. Run the Blender render step first.")
        sys.exit(1)
    JSON_PATH = candidates[0]
    print(f"Using most recent: {JSON_PATH}")

with open(JSON_PATH) as f: d = json.load(f)
img = Image.open(d['image']).convert('RGBA')
W, H = img.size
ov = Image.new('RGBA', (W, H), (0, 0, 0, 0))
dr = ImageDraw.Draw(ov)
try:
    font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 28)
except:
    font = ImageFont.load_default()

for el in d['elements']:
    bx = min(el['x1'], el['x2']) + 6
    by = min(el['y1'], el['y2']) + 6
    r = 22
    dr.ellipse([bx, by, bx + r*2, by + r*2],
               fill=(255, 230, 50, 230), outline=(20, 20, 20, 255), width=2)
    tb = dr.textbbox((0, 0), str(el['num']), font=font)
    tw, th = tb[2]-tb[0], tb[3]-tb[1]
    dr.text((bx + r - tw/2, by + r - th/2 - 3), str(el['num']),
            fill=(20, 20, 20, 255), font=font)

Image.alpha_composite(img, ov).convert('RGB').save(d['image'])
print(f"Overlay written: {d['image']}")
print("Legend:")
for el in d['elements']:
    print(f"  {el['num']}: {el['label']}")
