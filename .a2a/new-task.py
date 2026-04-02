#!/usr/bin/env python3
"""
new-task.py — Create a skeleton TASK-NNN.json and plan file for the Planner to fill in.

Usage:
  python .a2a/new-task.py "Task title here"
"""
import json
import sys
import datetime
import pathlib

A2A = pathlib.Path(__file__).parent
TASKS = A2A / "tasks"
PLANS = A2A / "plans"


def next_task_id():
    """Find the next unused TASK-NNN id."""
    status_file = A2A / "status.json"
    existing = set()

    if status_file.exists():
        status = json.loads(status_file.read_text(encoding="utf-8"))
        existing.update(status.get("completedTasks", []))
        if status.get("currentTask"):
            existing.add(status["currentTask"])

    # Also scan task files on disk (catches tasks not yet in status.json)
    for f in TASKS.glob("TASK-*.json"):
        existing.add(f.stem)
    for f in (TASKS / "archive").glob("TASK-*.json") if (TASKS / "archive").exists() else []:
        existing.add(f.stem)

    n = 1
    while f"TASK-{n:03d}" in existing:
        n += 1
    return f"TASK-{n:03d}"


def main():
    title = " ".join(sys.argv[1:]).strip() or "Untitled"
    task_id = next_task_id()
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()

    TASKS.mkdir(parents=True, exist_ok=True)
    PLANS.mkdir(parents=True, exist_ok=True)

    # --- Write task JSON ---
    task = {
        "taskId": task_id,
        "title": title,
        "description": "",
        "phase": "planning",
        "priority": "normal",
        "createdBy": "claude",
        "createdAt": now,
        "planFile": f".a2a/plans/{task_id}-plan.md",
        "context": {
            "categories": [],
            "affectedFiles": [],
            "affectedDataFiles": []
        },
        "successCriteria": [],
        "rollbackPlan": "none",
        "executionStartedAt": None,
        "executionCompletedAt": None,
        "feedbackFile": f".a2a/tasks/{task_id}-feedback.json",
        "review": {
            "verdict": None,
            "reviewedAt": None,
            "notes": None,
            "nextTaskId": None
        }
    }
    task_file = TASKS / f"{task_id}.json"
    task_file.write_text(json.dumps(task, indent=2), encoding="utf-8")

    # --- Write plan markdown skeleton ---
    plan_template = f"""# Plan: {task_id} — {title}
**Written by:** Claude (Planner)
**Date:** {now[:10]}
**Target agent:** Gemini (Executor)

## Objective
TODO: One paragraph describing what must be achieved and why.

## Pre-conditions
- [ ] TODO: Condition the Executor must verify before starting

## Steps

### Step 1 — TODO: Step name {{step-id: s1}} [Tier 1]
**Working directory:** ./
**Command:**
```bash
echo "TODO: replace with real command"
```
**Expected output:** TODO
**On failure:** Record error and stop

## Verification Tests

### Test 1 — TODO {{test-id: t1}}
```bash
echo "TODO: replace with real verification"
```
**Expected:** TODO

## Acceptance Criteria Checklist
- [ ] Criterion 1 -> PASS/FAIL: evidence

## Files to include in feedback
- TODO: List specific files the Executor must report on
"""
    plan_file = PLANS / f"{task_id}-plan.md"
    plan_file.write_text(plan_template, encoding="utf-8")

    # --- Update status.json ---
    status_file = A2A / "status.json"
    if status_file.exists():
        status = json.loads(status_file.read_text(encoding="utf-8"))
    else:
        status = {
            "protocolVersion": "1.0",
            "a2aEnabled": True,
            "queue": [],
            "completedTasks": []
        }

    status.update({
        "currentTask": task_id,
        "phase": "planning",
        "lastUpdated": now,
        "updatedBy": "claude",
        "notes": f"Planning {task_id}: {title}"
    })
    status_file.write_text(json.dumps(status, indent=2), encoding="utf-8")

    print(f"Created {task_id}: {title}")
    print(f"  Task spec : .a2a/tasks/{task_id}.json")
    print(f"  Plan file : .a2a/plans/{task_id}-plan.md")
    print()
    print("Next steps for the Planner:")
    print(f"  1. Fill in description, context, successCriteria in {task_id}.json")
    print(f"  2. Write the execution steps in {task_id}-plan.md")
    print(f"  3. Set phase to 'awaiting-execution' in {task_id}.json and status.json")
    print(f'  4. Run: python ".a2a/orchestrate.py" {task_id}')


if __name__ == "__main__":
    main()
