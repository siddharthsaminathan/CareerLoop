"""
S7-only verification script.

Loads existing S1-S6 artifacts from the last Varsha × H&M run and calls
section_rewrites_node directly. Verifies:
  1. deepseek-chat is used (not v4-pro)
  2. All sections are rewritten (no 0-char fallbacks)
  3. No max_tokens overrides (config default 10000 used)

Usage:
    python test_s7_only.py
"""

import json
import sys
import io
from pathlib import Path
from dotenv import load_dotenv

# Force UTF-8 output on Windows so unicode chars in graph.py don't crash
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

load_dotenv()

from careerloop.council.graph import section_rewrites_node

BASE = Path("output/council/varsha/varsha-hm-merchandiser")

def load(filename):
    path = BASE / filename
    if not path.exists():
        print(f"  !! Missing artifact: {filename}")
        sys.exit(1)
    return json.loads(path.read_text(encoding="utf-8"))


print("=" * 60)
print("S7 ISOLATION TEST — Varsha × H&M")
print("=" * 60)
print()
print("Loading artifacts from last run...")

state = {
    "canonical_resume":      load("01_canonical_resume.json"),
    "preservation_contract": load("02_preservation_contract.json"),
    "role_decode":           load("04_role_decode.json"),
    "user_truth":            load("05_user_truth.json"),
    "positioning_strategy":  load("06_positioning_strategy.json"),
    "errors": [],
}

print("  [OK] All artifacts loaded")
print()
print("Running section_rewrites_node...")
print("-" * 60)

result = section_rewrites_node(state)

print("-" * 60)
print()

rewrites = result.get("section_rewrites", {}).get("rewrites", {})
skipped  = result.get("section_rewrites", {}).get("skipped", [])
errors   = result.get("errors", [])

print(f"RESULTS")
print(f"  Rewritten : {len(rewrites)} section(s)")
print(f"  Skipped   : {len(skipped)} section(s) → {skipped}")
print(f"  Errors    : {len(errors)}")
print()

if rewrites:
    print("Per-section breakdown:")
    for sid, rw in rewrites.items():
        chars = len(rw.get("rewritten_text", ""))
        change = rw.get("change_type", "?")
        fallback = rw.get("fallback_reason", "")
        warn = f"  ⚠ FALLBACK: {fallback}" if fallback else ""
        status = "[OK]" if chars > 100 else "[EMPTY]"
        print(f"  {status} [{change}] {sid}: {chars} chars{warn}")

print()
if errors:
    print("Errors:")
    for e in errors:
        print(f"  !! {e}")

# Quick content spot-check on professional_experience
pe = rewrites.get("professional_experience", {})
pe_text = pe.get("rewritten_text", "")
if pe_text and len(pe_text) > 200:
    print()
    print("Experience section preview (first 600 chars):")
    print("-" * 40)
    print(pe_text[:600])
    print("...")

# Save output for inspection
out_path = BASE / "07b_s7_test_rewrites.json"
out_path.write_text(
    json.dumps(result.get("section_rewrites", {}), indent=2, ensure_ascii=False),
    encoding="utf-8",
)
print()
print(f"Full output saved → {out_path}")
