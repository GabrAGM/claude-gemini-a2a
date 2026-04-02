#!/usr/bin/env python3
"""
workflow-reminder.py — Injected by Claude Code UserPromptSubmit hook.
Shows A2A mode + status before every Claude response.
"""
import json, pathlib

A2A = pathlib.Path(__file__).parent
PROJECT_ROOT = A2A.parent
status_file = A2A / "status.json"
settings_file = PROJECT_ROOT / ".claude" / "settings.local.json"

try:
    status = json.loads(status_file.read_text(encoding="utf-8"))
    phase = status.get("phase", "unknown")
    current = status.get("currentTask", "none")
    a2a_on = status.get("a2aEnabled", True)
except Exception:
    phase = "unknown"
    current = "none"
    a2a_on = True

try:
    settings = json.loads(settings_file.read_text(encoding="utf-8"))
    hook_on = bool(settings.get("hooks", {}).get("UserPromptSubmit"))
except Exception:
    hook_on = False

hook_label = "ON  (/hook-off to disable)" if hook_on else "OFF (/hook-on to enable, then restart)"
a2a_label  = "ON  (/a2a-off to disable)" if a2a_on  else "OFF (/a2a-on to enable)"

print("=" * 62)
print(f"  Hook        : {hook_label}")
print(f"  A2A mode    : {a2a_label}")
print("=" * 62)

if a2a_on:
    print("  A2A MODE: ON  (Gemini is Executor)")
    print("=" * 62)
    print(f"  Phase        : {phase}")
    print(f"  Current task : {current}")
    print()
    print("  DELEGATION MODES:")
    print()
    print("  DIRECT (Claude acts alone):")
    print("  - Simple question / explanation")
    print("  - Single file read or quick lookup")
    print("  - Reviewing feedback / archiving tasks")
    print()
    print("  INVESTIGATE (Gemini explores, Claude concludes):")
    print("  - Search across many files or logs")
    print("  - Diagnose a bug or trace an issue")
    print("  - Cross-reference multiple data sources")
    print()
    print("  EXECUTE (Gemini runs, Claude reviews):")
    print("  - Write/modify files")
    print("  - Run scripts or exports")
    print("  - Multi-step operations (3+)")
    print("  - Tier 2 or Tier 3 operations")
    print()
    print("  State mode chosen + reason before acting.")
    print()
    if phase in ("executing", "awaiting-review"):
        print(f"  BLOCKED: phase='{phase}' for {current}.")
        print(f"  Resolve current task before starting a new one.")
        print()
    print("  Toggle: python .a2a/toggle.py off")
else:
    print("  A2A MODE: OFF  (Claude works directly)")
    print("=" * 62)
    print()
    print("  Claude handles ALL tasks directly without invoking Gemini.")
    print()
    print("  Toggle: python .a2a/toggle.py on")

print("=" * 62)
