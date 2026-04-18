"""
Nine-slice generator for Band Ritual rects.

GUARANTEE: zero stretching. Every output pixel is either:
  - an exact copy from the source (corners), OR
  - a crop from the source center (edges/interior when source >= target), OR
  - a tile-repeat of a source crop (when source < target — no stretching, just repetition)

Usage:
    python3 nine_slice_band_ritual.py SOURCE.png BORDER_PX OUTPUT_DIR [--scale 1]

    SOURCE.png    — the single large Gemini-generated texture with borders
    BORDER_PX     — approximate thickness (in px) of the border region in SOURCE
    OUTPUT_DIR    — where to write 23 per-rect PNGs
    --scale       — optional multiplier for target dimensions (default 1 = native rect size)

The list of rects and their native sizes is computed from /tmp/rect_groups.json
(produced earlier by the Blender analysis).
"""

import json
import os
import sys
from PIL import Image

# ------------- CONFIG -------------
RECTS_JSON = "/tmp/rect_groups.json"  # produced earlier from Blender
# ----------------------------------


def nine_slice(src: Image.Image, target_w: int, target_h: int, border: int,
               allow_tile: bool = True) -> Image.Image:
    """Apply 9-slice scaling (crop-only, optional tiling — NEVER stretch) to produce target size."""
    sw, sh = src.size

    # Clamp border so it can't exceed half of target on any axis
    b = max(1, min(border, target_w // 2, target_h // 2, sw // 2 - 1, sh // 2 - 1))

    # If border had to shrink, scale-crop the original border region accordingly (no stretch,
    # just take a thinner slice from the outer edge of the source).
    out = Image.new("RGBA", (target_w, target_h))

    # --- 4 CORNERS (exact copy) ---
    tl = src.crop((0, 0, b, b))
    tr = src.crop((sw - b, 0, sw, b))
    bl = src.crop((0, sh - b, b, sh))
    br = src.crop((sw - b, sh - b, sw, sh))
    out.paste(tl, (0, 0))
    out.paste(tr, (target_w - b, 0))
    out.paste(bl, (0, target_h - b))
    out.paste(br, (target_w - b, target_h - b))

    # --- 4 EDGES ---
    src_edge_w = sw - 2 * b
    src_edge_h = sh - 2 * b
    tgt_edge_w = target_w - 2 * b
    tgt_edge_h = target_h - 2 * b

    def paste_or_tile_horizontal(slice_img: Image.Image, dest_x: int, dest_y: int,
                                  target_pixels: int, source_pixels: int):
        """Place an image horizontally. If target > source, tile; else center-crop."""
        if target_pixels <= 0:
            return
        if target_pixels <= source_pixels:
            x_start = (source_pixels - target_pixels) // 2
            out.paste(slice_img.crop((x_start, 0, x_start + target_pixels, slice_img.height)),
                      (dest_x, dest_y))
        else:
            if not allow_tile:
                return
            filled = 0
            while filled < target_pixels:
                chunk = min(source_pixels, target_pixels - filled)
                out.paste(slice_img.crop((0, 0, chunk, slice_img.height)),
                          (dest_x + filled, dest_y))
                filled += chunk

    def paste_or_tile_vertical(slice_img: Image.Image, dest_x: int, dest_y: int,
                                target_pixels: int, source_pixels: int):
        if target_pixels <= 0:
            return
        if target_pixels <= source_pixels:
            y_start = (source_pixels - target_pixels) // 2
            out.paste(slice_img.crop((0, y_start, slice_img.width, y_start + target_pixels)),
                      (dest_x, dest_y))
        else:
            if not allow_tile:
                return
            filled = 0
            while filled < target_pixels:
                chunk = min(source_pixels, target_pixels - filled)
                out.paste(slice_img.crop((0, 0, slice_img.width, chunk)),
                          (dest_x, dest_y + filled))
                filled += chunk

    # Top edge (between top-left and top-right corners)
    top_strip = src.crop((b, 0, sw - b, b))
    paste_or_tile_horizontal(top_strip, b, 0, tgt_edge_w, src_edge_w)

    # Bottom edge
    bot_strip = src.crop((b, sh - b, sw - b, sh))
    paste_or_tile_horizontal(bot_strip, b, target_h - b, tgt_edge_w, src_edge_w)

    # Left edge
    left_strip = src.crop((0, b, b, sh - b))
    paste_or_tile_vertical(left_strip, 0, b, tgt_edge_h, src_edge_h)

    # Right edge
    right_strip = src.crop((sw - b, b, sw, sh - b))
    paste_or_tile_vertical(right_strip, target_w - b, b, tgt_edge_h, src_edge_h)

    # --- CENTER ---
    if tgt_edge_w > 0 and tgt_edge_h > 0:
        center_src = src.crop((b, b, sw - b, sh - b))
        cw, ch = center_src.size
        # Fill target center by cropping (if target fits) or tiling 2D
        if tgt_edge_w <= cw and tgt_edge_h <= ch:
            x_start = (cw - tgt_edge_w) // 2
            y_start = (ch - tgt_edge_h) // 2
            out.paste(center_src.crop((x_start, y_start,
                                       x_start + tgt_edge_w, y_start + tgt_edge_h)),
                      (b, b))
        else:
            if allow_tile:
                for yo in range(0, tgt_edge_h, ch):
                    for xo in range(0, tgt_edge_w, cw):
                        chunk_w = min(cw, tgt_edge_w - xo)
                        chunk_h = min(ch, tgt_edge_h - yo)
                        out.paste(center_src.crop((0, 0, chunk_w, chunk_h)),
                                  (b + xo, b + yo))

    return out


def main(source_path: str, border_px: int, out_dir: str, scale: float = 1.0):
    with open(RECTS_JSON) as f:
        groups = json.load(f)

    os.makedirs(out_dir, exist_ok=True)
    src = Image.open(source_path).convert("RGBA")

    flat = []  # all rect records
    for aspect_str, rects in groups.items():
        for r in rects:
            flat.append(r)

    count = 0
    for r in flat:
        target_w = max(8, int(round(r["px_w"] * scale)))
        target_h = max(8, int(round(r["px_h"] * scale)))
        out_img = nine_slice(src, target_w, target_h, border_px)
        out_path = os.path.join(out_dir, f"{r['name']}_texture.png")
        out_img.save(out_path)
        print(f"  {r['name']:25s} → {target_w}×{target_h}  ({out_path})")
        count += 1
    print(f"\nDone. {count} textures written to {out_dir}")


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: nine_slice_band_ritual.py SOURCE.png BORDER_PX OUTPUT_DIR [--scale N]")
        sys.exit(1)
    src = sys.argv[1]
    border = int(sys.argv[2])
    out = sys.argv[3]
    scale = 1.0
    if "--scale" in sys.argv:
        i = sys.argv.index("--scale")
        scale = float(sys.argv[i + 1])
    main(src, border, out, scale)
