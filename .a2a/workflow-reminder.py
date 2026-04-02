#!/usr/bin/env python3
"""
workflow-reminder.py — Injected by Claude Code UserPromptSubmit hook.
Compact 1-line status display. Claude has CLAUDE.md for full mode descriptions.
"""
import json, pathlib

A2A = pathlib.Path(__file__).parent
status_file = A2A / "status.json"

try:
    status = json.loads(status_file.read_text(encoding="utf-8"))
    phase = status.get("phase", "idle")
    current = status.get("currentTask") or "none"
    a2a_on = status.get("a2aEnabled", True)
except Exception:
    phase = "idle"
    current = "none"
    a2a_on = True

if a2a_on:
    blocked = " BLOCKED" if phase in ("executing", "awaiting-review", "needs-input") else ""
    print(f"[A2A ON | {phase} | {current}{blocked}]")
else:
    print("[A2A OFF]")
