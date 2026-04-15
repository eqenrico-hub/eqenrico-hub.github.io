"""
Image → 3D mesh via HuggingFace TRELLIS (Microsoft, SOTA 2024).
Free, no API key. GLB output ready for Blender import.

Workflow:
  1. Upload image
  2. TRELLIS preprocessing (bg removal)
  3. Image-to-3D generation (~30-90 sec on HF's GPU)
  4. Extract GLB mesh
  5. Download locally

Usage:
    python3 image_to_3d.py <input.png> [output_name]
"""
import sys, os, time, shutil
from pathlib import Path

try:
    from gradio_client import Client, handle_file
except ImportError:
    print("Install: pip3 install gradio_client --break-system-packages --user")
    sys.exit(1)

if len(sys.argv) < 2:
    print("Usage: python3 image_to_3d.py <input.png> [output_name]")
    sys.exit(1)

input_path = Path(sys.argv[1]).expanduser().resolve()
out_name = sys.argv[2] if len(sys.argv) > 2 else input_path.stem + "_3d"
out_path = Path("/Users/ricosan/Downloads") / f"{out_name}.glb"
preview_video = Path("/Users/ricosan/Downloads") / f"{out_name}_preview.mp4"

print(f"Input: {input_path.name}")
print("Connecting to HuggingFace JeffreyXiang/TRELLIS...")
client = Client("JeffreyXiang/TRELLIS", verbose=False)

print("\n[1/4] Starting session...")
try:
    client.predict(api_name="/start_session")
except Exception as e:
    print(f"  session start warning (ok): {e}")

print("[2/4] Preprocessing image (removing background)...")
prep = client.predict(
    image=handle_file(str(input_path)),
    api_name="/preprocess_image"
)
print(f"  → preprocessed: {prep}")

print("[3/4] Generating 3D (this takes ~30-90 seconds)...")
t0 = time.time()
result = client.predict(
    image=handle_file(prep),
    multiimages=[],
    seed=0,
    ss_guidance_strength=7.5,
    ss_sampling_steps=12,
    slat_guidance_strength=3.0,
    slat_sampling_steps=12,
    multiimage_algo="stochastic",
    api_name="/image_to_3d"
)
print(f"  → generated in {time.time()-t0:.1f}s")
# result is dict with video preview
if isinstance(result, dict) and 'video' in result:
    shutil.copy(result['video'], preview_video)
    print(f"  Preview video: {preview_video}")

print("[4/4] Extracting GLB mesh...")
glb_result = client.predict(
    mesh_simplify=0.95,
    texture_size=1024,
    api_name="/extract_glb"
)
# glb_result is tuple: (viewer_file, download_file)
glb_src = None
if isinstance(glb_result, (list, tuple)):
    for item in glb_result:
        if isinstance(item, str) and item.endswith(".glb"):
            glb_src = item
            break
elif isinstance(glb_result, str) and glb_result.endswith(".glb"):
    glb_src = glb_result

if glb_src:
    shutil.copy(glb_src, out_path)
    print(f"\n✓ GLB saved: {out_path}")
    print(f"✓ Preview: {preview_video}")
    print(f"\nOpening both for your evaluation...")
    os.system(f"open '{preview_video}'")
    time.sleep(1)
    os.system(f"open '{input_path}'")
    print("\nIf approved, tell Claude to import into Blender.")
else:
    print(f"Unexpected GLB extraction result: {glb_result}")
    sys.exit(1)
