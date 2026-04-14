#!/usr/bin/env python3
"""World generator agent — orchestrates PixelLab tileset generation + Wang auto-detection."""
import json
import os
import sys
import time
import uuid
from http.server import HTTPServer, BaseHTTPRequestHandler
from PIL import Image
import requests

PIXELLAB_URL = "https://api.pixellab.ai/mcp"
PIXELLAB_TOKEN = os.environ.get("PIXELLAB_TOKEN", "")  # export PIXELLAB_TOKEN=... before running
if not PIXELLAB_TOKEN:
    print("WARNING: PIXELLAB_TOKEN env var not set. PixelLab calls will fail.", file=__import__('sys').stderr)
TEMPLATES_DIR = os.environ.get("TEMPLATES_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates", "variants"))
MAX_RETRIES = 2
POLL_INTERVAL = 10
POLL_TIMEOUT = 300  # 5 minutes

# --------------------------------------------------------------------
# Theme → (lower_description, upper_description) derivation
# --------------------------------------------------------------------
# Keyword-based mapping of common themes to terrain descriptions.
# The UPPER is the "overlay" (streets/walls/trees). The LOWER is the "ground"
# (where buildings sit). For best results, the two should contrast visually.
THEME_MAP = [
    # (keywords, tier0 path, tier1 main, tier2 elevated, tier3 peak)
    (["desert", "sand", "dune", "sahara"],
     "cracked sand path with small stones",
     "rolling sand dunes with dry shrubs",
     "rocky sandstone plateau with cracks",
     "tall red-rock cliff with jagged peaks"),
    (["ice", "frost", "snow", "glacier", "arctic", "frozen", "crystal"],
     "packed snow and frozen dirt path",
     "fresh snow field with small icicles",
     "jagged ice crystals and frost boulders",
     "tall glacier cliff with ice spires"),
    (["lava", "volcanic", "volcano", "magma", "fire"],
     "dark cracked earth with ash",
     "volcanic rock with glowing lava seams",
     "obsidian boulders with molten veins",
     "erupting volcanic peak with lava flows"),
    (["dark", "shadow", "void", "evil", "cursed", "haunted", "dead", "cemetery"],
     "dark stone path with faint glow",
     "withered grass with dead leaves",
     "twisted dead trees with dark shadows",
     "cursed obsidian spires with purple mist"),
    (["forest", "wood", "tree", "jungle", "mossy"],
     "muddy dirt path with moss",
     "lush green grass with wildflowers",
     "dense dark forest with tall pine trees",
     "rocky forest cliff with gnarled roots"),
    (["mushroom", "fungi", "spore"],
     "mossy ground path with tiny fungi",
     "soft moss carpet with small mushrooms",
     "giant glowing mushrooms with purple spores",
     "towering mushroom mountain with spore clouds"),
    (["cyber", "neon", "tech", "digital", "synthwave", "future"],
     "dark metallic floor with neon lines",
     "glass panels with data circuits",
     "neon-lit cyberpunk buildings",
     "tall holographic skyscrapers with neon signs"),
    (["water", "ocean", "sea", "coral", "underwater", "reef"],
     "sandy seafloor with pebbles",
     "grassy underwater meadow with seagrass",
     "colorful coral reef",
     "tall kelp pillar with glowing anemones"),
    (["swamp", "marsh", "bog", "toxic", "poison"],
     "muddy swamp path with algae",
     "wet marsh grass with lily pads",
     "twisted swamp trees with toxic green mist",
     "tall dead cypress tower with hanging moss"),
    (["candy", "sweet", "sugar", "pastel"],
     "soft pink candy path with sprinkles",
     "cotton candy grass with gumdrops",
     "giant lollipops and candy cane trees",
     "frosting-topped cake mountain"),
    (["steampunk", "brass", "copper", "gear"],
     "cobblestone path with brass plating",
     "patchy metal grass with rivets",
     "steampunk machinery with brass gears",
     "tall chimney tower with copper domes"),
    (["grass", "meadow", "pasture", "field"],
     "dirt path through short grass",
     "lush tall grass with wildflowers",
     "rolling hills with scattered rocks",
     "tall grassy cliff with standing stones"),
]

def derive_4tier_descriptions(prompt):
    """Given a short world theme, return (tier0, tier1, tier2, tier3) descriptions."""
    p = prompt.lower()
    for entry in THEME_MAP:
        keywords = entry[0]
        if any(k in p for k in keywords):
            t0, t1, t2, t3 = entry[1], entry[2], entry[3], entry[4]
            # Blend user's exact wording into tier2 (the most visible overlay)
            return t0, t1, f"{t2}, {prompt}", t3
    # Generic fallback
    return (
        "dirt path with pebbles",
        "lush green grass with wildflowers",
        prompt,
        f"tall rocky peak above {prompt}",
    )

# --------------------------------------------------------------------
# PixelLab MCP client
# --------------------------------------------------------------------
def mcp_call(method, params, req_id=1):
    payload = {"jsonrpc": "2.0", "method": method, "params": params, "id": req_id}
    headers = {
        "Authorization": f"Bearer {PIXELLAB_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    r = requests.post(PIXELLAB_URL, json=payload, headers=headers, stream=True, timeout=180)
    r.raise_for_status()
    # SSE stream: many `data: {...}` lines. The one we want has "result" in it
    # (others are notifications/message for logging)
    result_msg = None
    for line in r.iter_lines():
        if not line or not line.startswith(b"data: "):
            continue
        try:
            obj = json.loads(line[6:].decode("utf-8"))
        except Exception:
            continue
        if "result" in obj or "error" in obj:
            result_msg = obj
            # Got the final result — can stop reading
            break
    if result_msg is None:
        raise RuntimeError("No result in SSE stream")
    if "error" in result_msg:
        raise RuntimeError(f"MCP error: {result_msg['error']}")
    return result_msg

def create_tileset(lower_desc, upper_desc, lower_base_tile_id=None, transition_size=0.0):
    """Queue a tileset generation. Returns (tileset_id, upper_base_tile_id)."""
    import re
    args = {
        "lower_description": lower_desc,
        "upper_description": upper_desc,
        "tile_size": {"width": 32, "height": 32},
        "shading": "detailed shading",
        "view": "high top-down",
        "transition_size": transition_size,
    }
    if transition_size > 0:
        args["transition_description"] = f"blend of {lower_desc} and {upper_desc}"
    if lower_base_tile_id:
        args["lower_base_tile_id"] = lower_base_tile_id
    resp = mcp_call("tools/call", {"name": "create_topdown_tileset", "arguments": args})
    content = resp.get("result", {}).get("content", [])
    text = "".join(c.get("text", "") for c in content if c.get("type") == "text")

    # Parse tileset ID (first UUID after "Tileset ID:")
    ts_id = None
    m = re.search(r"Tileset ID:\**\s*`?([0-9a-f-]{36})`?", text)
    if m:
        ts_id = m.group(1)
    else:
        m = re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", text)
        if m: ts_id = m.group(0)

    # Parse upper base tile ID (for chaining). Look for "- Upper (...): `<uuid>`"
    upper_id = None
    m = re.search(r"-\s*Upper\s*\([^)]*\):\s*`([0-9a-f-]{36})`", text)
    if m:
        upper_id = m.group(1)
    else:
        # Fallback — all UUIDs, the last one is usually the upper
        uuids = re.findall(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", text)
        if len(uuids) >= 3:
            upper_id = uuids[-1]

    if not ts_id:
        raise RuntimeError(f"Could not parse tileset_id from: {text[:400]}")
    return ts_id, upper_id

def poll_tileset(tileset_id, on_progress=None):
    """Poll until the tileset is completed. Returns (png_bytes, raw_text).

    The completed response embeds the PNG as base64 in a content[type=image] entry.
    The "still processing" response starts with ⏳ emoji and contains "Tileset is still being generated".
    """
    import re, base64
    start = time.time()
    while time.time() - start < POLL_TIMEOUT:
        resp = mcp_call("tools/call", {"name": "get_topdown_tileset", "arguments": {"tileset_id": tileset_id}}, req_id=2)
        content = resp.get("result", {}).get("content", [])
        text = ""
        image_b64 = None
        for c in content:
            if c.get("type") == "text":
                text += c.get("text", "")
            elif c.get("type") == "image" and c.get("data"):
                image_b64 = c["data"]
        # If the response has an embedded image, we're done
        if image_b64:
            return base64.b64decode(image_b64), text
        # Check if still processing — the ONLY reliable marker is "is still being generated"
        if "is still being generated" in text.lower() or "still being" in text.lower():
            pct_m = re.search(r"(\d+)%", text)
            eta_m = re.search(r"ETA:\s*~?(\d+)", text)
            pct = pct_m.group(1) if pct_m else "?"
            eta = eta_m.group(1) if eta_m else "?"
            if on_progress: on_progress(f"Processing... {pct}% (ETA ~{eta}s)")
            time.sleep(POLL_INTERVAL)
            continue
        # No image and no "still generating" — unexpected state. Wait and retry.
        if on_progress: on_progress("Waiting for tileset...")
        time.sleep(POLL_INTERVAL)
    raise RuntimeError(f"Tileset {tileset_id} did not complete in {POLL_TIMEOUT}s")

def download_png(url, dest):
    headers = {"Authorization": f"Bearer {PIXELLAB_TOKEN}"}
    r = requests.get(url, headers=headers, timeout=60)
    r.raise_for_status()
    with open(dest, "wb") as f:
        f.write(r.content)

# --------------------------------------------------------------------
# Building generation via create_map_object
# --------------------------------------------------------------------
STANDARD_BUILDINGS = [
    "tavern", "library", "windmill", "palace", "forge",
    "temple", "market", "tower", "observatory", "stables",
]

def derive_building_prompts(world_prompt, context, explicit_list):
    """Decide what 10 buildings to generate.
    - explicit_list: if user provided a comma-separated list of 10+ buildings, use that
    - context: use as flavor layered over standard buildings
    - fallback: just standard buildings flavored with world_prompt
    """
    if explicit_list:
        items = [x.strip() for x in explicit_list.split(",") if x.strip()]
        if len(items) >= 3:
            return [(f"b{i}_" + items[i][:16].replace(" ", "_"), items[i]) for i in range(min(10, len(items)))]
    # Use standard names with context flavor
    flavor = context if context else world_prompt
    result = []
    for name in STANDARD_BUILDINGS:
        desc = f"{flavor} style {name}" if flavor else name
        result.append((name, desc))
    return result

def create_building(description, size=128):
    """Queue a map object (building) generation. Returns object_id."""
    import re
    args = {
        "description": description,
        "width": size, "height": size,
        "view": "high top-down",
        "outline": "selective outline",
        "shading": "detailed shading",
    }
    resp = mcp_call("tools/call", {"name": "create_map_object", "arguments": args}, req_id=10)
    content = resp.get("result", {}).get("content", [])
    text = "".join(c.get("text", "") for c in content if c.get("type") == "text")
    m = re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", text)
    if m:
        return m.group(0)
    raise RuntimeError(f"No object_id in response: {text[:300]}")

def poll_building(object_id, on_progress=None):
    """Poll for a map object until completed. Returns PNG bytes."""
    import re, base64
    start = time.time()
    while time.time() - start < POLL_TIMEOUT:
        resp = mcp_call("tools/call", {"name": "get_map_object", "arguments": {"object_id": object_id}}, req_id=11)
        content = resp.get("result", {}).get("content", [])
        text = ""
        image_b64 = None
        for c in content:
            if c.get("type") == "text":
                text += c.get("text", "")
            elif c.get("type") == "image" and c.get("data"):
                image_b64 = c["data"]
        if image_b64:
            return base64.b64decode(image_b64)
        if "being generated" in text.lower() or "still" in text.lower() and "queue" not in text.lower():
            if on_progress: on_progress(f"Building {object_id[:8]} still generating...")
            time.sleep(5)
            continue
        time.sleep(5)
    raise RuntimeError(f"Building {object_id} did not complete")

# --------------------------------------------------------------------
# Tile analysis (Python port of tile-diagnostic.html algorithm)
# --------------------------------------------------------------------
TS = 32

def sample_corners(img):
    """Return list of 16 dicts: {col, row, corners: {nw, ne, sw, se}}"""
    arr = img.convert("RGB").load()
    tiles = []
    for row in range(4):
        for col in range(4):
            ox, oy = col * TS, row * TS
            def avg(cx, cy):
                r = g = b = count = 0
                for dy in range(6):
                    for dx in range(6):
                        px = arr[cx + dx, cy + dy]
                        r += px[0]; g += px[1]; b += px[2]; count += 1
                return {"r": r / count, "g": g / count, "b": b / count}
            tiles.append({
                "col": col, "row": row,
                "corners": {
                    "nw": avg(ox + 1, oy + 1),
                    "ne": avg(ox + 25, oy + 1),
                    "sw": avg(ox + 1, oy + 25),
                    "se": avg(ox + 25, oy + 25),
                }
            })
    return tiles

def dist(a, b):
    return ((a["r"] - b["r"]) ** 2 + (a["g"] - b["g"]) ** 2 + (a["b"] - b["b"]) ** 2) ** 0.5

def lum(c):
    return 0.299 * c["r"] + 0.587 * c["g"] + 0.114 * c["b"]

def avg_color(arr):
    r = g = b = 0
    for c in arr: r += c["r"]; g += c["g"]; b += c["b"]
    n = len(arr)
    return {"r": r / n, "g": g / n, "b": b / n}

def flip_idx(idx, fh, fv):
    nw = (idx >> 3) & 1; ne = (idx >> 2) & 1; sw = (idx >> 1) & 1; se = idx & 1
    if fh: nw, ne = ne, nw; sw, se = se, sw
    if fv: nw, sw = sw, nw; ne, se = se, ne
    return nw * 8 + ne * 4 + sw * 2 + se

def compute_wang_map(img):
    """Returns (wang_map, unique_count, reason)."""
    tiles = sample_corners(img)

    tvars = []
    for t in tiles:
        corners = [t["corners"]["nw"], t["corners"]["ne"], t["corners"]["sw"], t["corners"]["se"]]
        mean = avg_color(corners)
        variance = sum(dist(c, mean) ** 2 for c in corners)
        tvars.append({"tile": t, "variance": variance, "mean": mean})
    tvars.sort(key=lambda x: x["variance"])
    solid_a = tvars[0]
    solid_b = tvars[1]
    for tv in tvars[1:]:
        if dist(tv["mean"], solid_a["mean"]) > dist(solid_b["mean"], solid_a["mean"]):
            solid_b = tv
            break

    lum_a, lum_b = lum(solid_a["mean"]), lum(solid_b["mean"])
    grass_center = solid_a["mean"] if lum_a >= lum_b else solid_b["mean"]
    wood_center = solid_b["mean"] if lum_a >= lum_b else solid_a["mean"]

    all_corners = []
    for ti, t in enumerate(tiles):
        for key in ("nw", "ne", "sw", "se"):
            c = t["corners"][key]
            dg = dist(c, grass_center); dw = dist(c, wood_center)
            all_corners.append({"ti": ti, "key": key, "grassiness": dw / (dg + dw + 0.001)})
    sorted_corners = sorted(all_corners, key=lambda x: -x["grassiness"])

    def classify(top_n, invert):
        order = sorted(all_corners, key=lambda x: x["grassiness"]) if invert else sorted_corners
        grass_set = set(f"{c['ti']}_{c['key']}" for c in order[:top_n])
        wmap = {}
        for ti, t in enumerate(tiles):
            cv = {k: 1 if f"{ti}_{k}" in grass_set else 0 for k in ("nw", "ne", "sw", "se")}
            idx = cv["nw"] * 8 + cv["ne"] * 4 + cv["sw"] * 2 + cv["se"]
            if idx not in wmap:
                wmap[idx] = {"x": t["col"], "y": t["row"]}
        return wmap

    best_map, best_count = None, 0
    for split in (32, 31, 33, 30, 34):
        for inv in (False, True):
            wm = classify(split, inv)
            if len(wm) > best_count:
                best_count = len(wm); best_map = wm
            if best_count == 16: break
        if best_count == 16: break

    # Polarity check: idx 15 (all grass) must be brighter than idx 0 (all wood)
    if best_map and 0 in best_map and 15 in best_map:
        t15 = next((t for t in tiles if t["col"] == best_map[15]["x"] and t["row"] == best_map[15]["y"]), None)
        t0 = next((t for t in tiles if t["col"] == best_map[0]["x"] and t["row"] == best_map[0]["y"]), None)
        if t15 and t0:
            l15 = lum(avg_color([t15["corners"][k] for k in ("nw","ne","sw","se")]))
            l0 = lum(avg_color([t0["corners"][k] for k in ("nw","ne","sw","se")]))
            if l0 > l15:
                best_map = {15 - k: v for k, v in best_map.items()}

    # Derive missing with flips
    for idx in range(16):
        if idx in best_map: continue
        for fh, fv in ((True, False), (False, True), (True, True)):
            src = flip_idx(idx, fh, fv)
            if src in best_map and not best_map[src].get("flipH") and not best_map[src].get("flipV"):
                e = dict(best_map[src]); e["flipH"] = fh; e["flipV"] = fv
                best_map[idx] = e
                break

    return best_map, best_count

# --------------------------------------------------------------------
# HTTP server
# --------------------------------------------------------------------
class AgentHandler(BaseHTTPRequestHandler):
    def _set_cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(200); self._set_cors(); self.end_headers()

    def do_POST(self):
        if self.path != "/create-world":
            self.send_response(404); self._set_cors(); self.end_headers(); return
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length))
        prompt = body.get("prompt", "").strip()
        buildings_mode = body.get("buildingsMode", "standard")  # standard / custom / none
        buildings_context = body.get("buildingsContext", "").strip()
        if not prompt:
            self.send_response(400); self._set_cors(); self.end_headers()
            self.wfile.write(b'{"error":"prompt required"}'); return

        # Derive 4 tier descriptions for 3 chained tilesets
        tier0, tier1, tier2, tier3 = derive_4tier_descriptions(prompt)

        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson")
        self._set_cors(); self.end_headers()

        def log(msg, **extra):
            line = {"msg": msg, **extra}
            self.wfile.write((json.dumps(line) + "\n").encode()); self.wfile.flush()

        try:
            log(f"Theme: '{prompt}'")
            log(f"→ Tier 0 (path): '{tier0}'")
            log(f"→ Tier 1 (main): '{tier1}'")
            log(f"→ Tier 2 (elevated): '{tier2}'")
            log(f"→ Tier 3 (peak): '{tier3}'")

            # Generate 3 chained tilesets
            tier_descs = [(tier0, tier1), (tier1, tier2), (tier2, tier3)]
            tileset_keys = []
            wang_maps = []
            prev_upper_base_id = None
            base_ts = int(time.time())

            for ts_i, (lower_desc, upper_desc) in enumerate(tier_descs, start=1):
                log(f"--- Tileset {ts_i}/3: '{lower_desc}' ↔ '{upper_desc}' ---")
                wang_map = None
                png_bytes = None
                for attempt in range(1, MAX_RETRIES + 2):
                    log(f"Attempt {attempt}/{MAX_RETRIES + 1}: calling PixelLab...")
                    tileset_id, upper_base_id = create_tileset(lower_desc, upper_desc, lower_base_tile_id=prev_upper_base_id)
                    log(f"Got tileset_id: {tileset_id[:8]}... Polling (~100s)...")
                    png_bytes, _ = poll_tileset(tileset_id, on_progress=lambda m: log(m))
                    import io
                    img = Image.open(io.BytesIO(png_bytes))
                    wang_map, unique_count = compute_wang_map(img)
                    log(f"Found {unique_count} unique Wang indices.")
                    if unique_count >= 14:
                        log(f"Tileset {ts_i} complete.")
                        break
                    if attempt > MAX_RETRIES:
                        log(f"Max retries reached for tileset {ts_i}. Filling gaps with flips.")
                        break
                    log(f"Incomplete, retrying...")

                ts_key = f"agent-{base_ts}-t{ts_i}-{tileset_id[:8]}"
                png_path = os.path.join(TEMPLATES_DIR, f"{ts_key}.png")
                with open(png_path, "wb") as f:
                    f.write(png_bytes)
                log(f"Saved tileset {ts_i} → {ts_key}.png")
                tileset_keys.append(ts_key)
                wang_maps.append(wang_map)

                # Next tileset uses this one's upper as its lower
                prev_upper_base_id = upper_base_id
                if prev_upper_base_id:
                    log(f"  Chain: next tileset's lower_base_tile_id = {prev_upper_base_id[:8]}...")

            # Buildings generation (optional)
            buildings_out = {}
            buildings_dir = None
            primary_key = tileset_keys[1] if len(tileset_keys) > 1 else tileset_keys[0]  # use tier1 key as reference
            if buildings_mode != "none":
                log(f"--- Buildings phase (mode: {buildings_mode}) ---")
                if buildings_mode == "standard":
                    building_plan = [(n, f"{prompt} style {n}") for n in STANDARD_BUILDINGS]
                else:
                    building_plan = derive_building_prompts(prompt, buildings_context, buildings_context if "," in buildings_context else "")
                log(f"Generating {len(building_plan)} buildings. This will take several minutes...")
                obj_ids = []
                for name, desc in building_plan:
                    try:
                        oid = create_building(desc, size=128)
                        obj_ids.append((name, desc, oid))
                        log(f"  queued {name}: '{desc[:60]}' → {oid[:8]}")
                    except Exception as e:
                        log(f"  FAILED to queue {name}: {e}")
                buildings_dir = os.path.join(TEMPLATES_DIR, "..", f"agent-buildings-{primary_key}")
                os.makedirs(buildings_dir, exist_ok=True)
                for name, desc, oid in obj_ids:
                    try:
                        png = poll_building(oid, on_progress=lambda m: log(m))
                        path = os.path.join(buildings_dir, f"{name}.png")
                        with open(path, "wb") as f: f.write(png)
                        buildings_out[name] = path
                        log(f"  ✓ {name} complete")
                    except Exception as e:
                        log(f"  ✗ {name} failed: {e}")

            log("Done!",
                tileset_key=primary_key,
                tileset_keys=tileset_keys,
                wang_maps=wang_maps,
                tiers=[tier0, tier1, tier2, tier3],
                buildings=list(buildings_out.keys()),
                buildings_dir=os.path.basename(buildings_dir) if buildings_dir else None)
        except Exception as e:
            import traceback
            log(f"ERROR: {e}", traceback=traceback.format_exc())

    def log_message(self, fmt, *args):
        print(f"[{self.address_string()}] {fmt % args}", file=sys.stderr)

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8766
    os.makedirs(TEMPLATES_DIR, exist_ok=True)
    print(f"World agent on http://localhost:{port}")
    HTTPServer(("", port), AgentHandler).serve_forever()
