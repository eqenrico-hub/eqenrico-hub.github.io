---
layout: default
title: MapBuilder Agent
---

# 🤖 MapBuilder Agent

A single-prompt world generator. Describe any theme — "dark forest", "cyberpunk alley", "volcanic ruins" — and the agent orchestrates the full pipeline: calls PixelLab API, validates the output, fills gaps, optionally generates matching buildings, and opens a map editor pre-loaded with the new world.

---

## What it does

| Stage | Detail |
|---|---|
| **1. Theme split** | Keyword-based rules map your single prompt into a (lower, upper) terrain pair PixelLab expects |
| **2. Tileset generation** | Calls PixelLab MCP `create_topdown_tileset`, polls every 10s (~100s total) |
| **3. Auto-detection** | Python port of our canvas analyzer — samples 4 corners of each of 16 tiles, clusters by terrain using solid-tile anchors |
| **4. Validation** | Counts unique Wang indices. If <14, regenerates up to **2 retries** |
| **5. Flip derivation** | For any still-missing indices (e.g. grass-BL, grass-TR that PixelLab sometimes skips), flips existing tiles |
| **6. Polarity check** | Ensures brighter tile = grass (idx 15), inverts map if needed |
| **7. Buildings (optional)** | Generates 10 buildings via `create_map_object` — either standard set or custom based on user context |
| **8. Handoff** | Saves WANG_MAP to localStorage, opens editor with `?tileset=X&autogen=1` |

---

## Architecture

Three local components:

```
┌─ Port 8765 ─┐   ┌─ Port 8766 ─┐   ┌─ browser ──┐
│ cors_server │   │ world_agent │   │ world-     │
│ (static)    │   │ (orchestrator)│  │ creator.html│
└─────────────┘   └─────────────┘   └─────────────┘
       ↓                 ↓                 ↓
  serves HTML/PNG   → PixelLab MCP ←  user prompt
                    → Pillow analysis
                    → retry loop
```

---

## Running locally

```bash
# 1. Static server for the HTML UI
cd ~/Desktop && python3 cors_server.py 8765 &

# 2. Orchestration agent
cd ~/Desktop/village-map-generator && python3 world_agent.py 8766 &

# 3. Open the UI
open "http://localhost:8765/village-map-generator/world-creator.html"
```

Requires Python 3, `Pillow`, `requests`, and a PixelLab API token.

---

## Key files

- `world_agent.py` — Python orchestrator with PixelLab MCP client, Wang analysis, flip derivation
- `world-creator.html` — prompt UI with theme chips + building options
- `v2.html` — map editor (edits the generated world)
- `tile-configurator.html` — manual tile assignment fallback
- `tile-diagnostic.html` — visual debugger for the detection algorithm

---

## Lessons

- **PixelLab doesn't always generate all 16 Wang corners.** Some tilesets genuinely miss idx 2 (grass BL) and idx 4 (grass TR). Flip derivation is not a workaround — it's mathematically equivalent.
- **Luminance ≠ terrain type.** Initial heuristic "brighter = grass" works for most tilesets but fails for low-contrast sets (e.g., Shadow Keep). Polarity post-check via the render inversion convention is required.
- **MCP over JSON-RPC SSE** returns many `data: {...}` events per call (notifications + final result). Client must consume all and pick the one with `result`.
- **Response format quirk**: completed tilesets return the PNG as embedded base64 inside a `content[type=image]` entry — no separate download needed.
