#!/usr/bin/env python3
"""
toggle.py — Enable or disable the A2A workflow.

Usage:
  python .a2a/toggle.py on      # Claude delegates to Gemini
  python .a2a/toggle.py off     # Claude works directly
  python .a2a/toggle.py         # Show current mode
"""
import json, sys, datetime, pathlib

A2A = pathlib.Path(__file__).parent
status_file = A2A / "status.json"

status = json.loads(status_file.read_text(encoding="utf-8"))
current = status.get("a2aEnabled", True)

if len(sys.argv) < 2:
    mode = "ON" if current else "OFF"
    print(f"A2A workflow is currently: {mode}")
    print(f"  python .a2a/toggle.py on   — delegate tasks to Gemini")
    print(f"  python .a2a/toggle.py off  — Claude works directly")
    sys.exit(0)

arg = sys.argv[1].strip().lower()
if arg not in ("on", "off"):
    print(f"Usage: python .a2a/toggle.py on|off")
    sys.exit(1)

new_value = arg == "on"
if new_value == current:
    print(f"A2A is already {'ON' if new_value else 'OFF'}. No change.")
    sys.exit(0)

status["a2aEnabled"] = new_value
status["lastUpdated"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
status["updatedBy"] = "human"
status_file.write_text(json.dumps(status, indent=2), encoding="utf-8")

if new_value:
    print("A2A workflow: ON")
    print("  Claude will plan tasks and delegate execution to Gemini.")
else:
    print("A2A workflow: OFF")
    print("  Claude will work directly without invoking Gemini.")
