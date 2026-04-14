"""
Validate a ChatGPT table response against the section's element list.

Catches:
  - Duplicate element names (e.g. two CHORD AMOUNT rows)
  - Elements NOT in the input list (e.g. hallucinated VARIATION)
  - Coordinates out of bounds (W+X > section width)
  - Malformed rows

Usage:
    python3 validate_table.py <section_key> <path_to_pasted_table.txt>

Exits 0 if clean, prints issues and exits 1 if problems found.
"""
import json, sys, re
from pathlib import Path

if len(sys.argv) < 3:
    print("Usage: python3 validate_table.py <section_key> <table_file>")
    sys.exit(2)

section_key = sys.argv[1]
table_path = sys.argv[2]

AGENT_DIR = Path(__file__).parent
with open(AGENT_DIR / "sections.json") as f: reg = json.load(f)
if section_key not in reg["sections"]:
    print(f"Unknown section: {section_key}")
    sys.exit(2)

section = reg["sections"][section_key]
expected_labels = {e[1].upper().strip() for e in section["elements"]}
w_mm, h_mm = map(int, section["expected_size_mm"].split("x"))

with open(table_path) as f: text = f.read()

# Parse table rows
rows = []
for line in text.splitlines():
    parts = [p.strip() for p in line.split("|")]
    if len(parts) < 7 or not parts[0].isdigit(): continue
    try:
        rows.append({
            "num": int(parts[0]), "name": parts[1].upper(), "type": parts[2].lower(),
            "x": float(parts[3]), "y": float(parts[4]),
            "w": float(parts[5]), "h": float(parts[6]),
            "notes": parts[7] if len(parts) > 7 else ""
        })
    except ValueError:
        print(f"! Malformed row: {line}")

issues = []
seen_names = {}
for r in rows:
    # Duplicates
    if r["name"] in seen_names:
        issues.append(f"DUPLICATE: '{r['name']}' appears twice (rows #{seen_names[r['name']]} and #{r['num']})")
    seen_names[r["name"]] = r["num"]
    # Hallucinated elements
    if r["name"] not in expected_labels:
        issues.append(f"HALLUCINATED: '{r['name']}' is not in the section's element list. Expected: {sorted(expected_labels)}")
    # Bounds
    if r["x"] + r["w"] > w_mm + 1:
        issues.append(f"OUT OF BOUNDS: '{r['name']}' X({r['x']}) + W({r['w']}) = {r['x']+r['w']} > section width {w_mm}mm")
    if r["y"] + r["h"] > h_mm + 1:
        issues.append(f"OUT OF BOUNDS: '{r['name']}' Y({r['y']}) + H({r['h']}) = {r['y']+r['h']} > section height {h_mm}mm")
    if r["x"] < 0 or r["y"] < 0:
        issues.append(f"NEGATIVE COORD: '{r['name']}' X={r['x']} Y={r['y']}")

# Missing elements (warn only — removal is allowed)
returned = set(seen_names.keys())
missing = expected_labels - returned
if missing:
    print(f"Note: elements removed from design (OK if intentional): {sorted(missing)}")

if issues:
    print(f"\n✗ {len(issues)} issue(s) in ChatGPT table response:")
    for i in issues: print(f"  - {i}")
    print("\nFix the table and re-run before apply.py.")
    sys.exit(1)
else:
    print(f"\n✓ Table valid: {len(rows)} elements, all in bounds, no duplicates, no hallucinations.")
    sys.exit(0)
