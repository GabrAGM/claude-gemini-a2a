#!/usr/bin/env python3
"""
orchestrate.py — Planner (Claude) invokes this to run the Executor (Gemini) non-interactively.

Usage:
  python .a2a/orchestrate.py TASK-001
  python .a2a/orchestrate.py TASK-001 --timeout 1200
"""
import subprocess
import sys
import json
import datetime
import pathlib
import argparse
import shlex

PROJECT_ROOT = pathlib.Path(__file__).parent.parent
A2A = PROJECT_ROOT / ".a2a"


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def main():
    parser = argparse.ArgumentParser(description="Invoke Gemini CLI on a task.")
    parser.add_argument("task_id", help="Task ID, e.g. TASK-001")
    parser.add_argument("--timeout", type=int, default=600,
                        help="Max seconds to wait for Gemini (default: 600)")
    args = parser.parse_args()

    task_id = args.task_id
    task_file = A2A / "tasks" / f"{task_id}.json"
    plan_file = A2A / "plans" / f"{task_id}-plan.md"
    log_file = A2A / "logs" / f"{task_id}-gemini.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)

    # --- Pre-condition checks ---
    if not task_file.exists():
        print(f"[orchestrate] ERROR: {task_file} not found. Planner must write it first.")
        sys.exit(1)
    if not plan_file.exists():
        print(f"[orchestrate] ERROR: {plan_file} not found. Planner must write it first.")
        sys.exit(1)

    task = json.loads(task_file.read_text(encoding="utf-8"))
    phase = task.get("phase")
    if phase != "awaiting-execution":
        print(f"[orchestrate] ERROR: Task phase is '{phase}', expected 'awaiting-execution'.")
        print(f"[orchestrate] Check .a2a/status.json and .a2a/tasks/{task_id}.json.")
        sys.exit(1)

    # --- Build context file for Executor ---
    criteria = task.get("successCriteria", [])
    context = task.get("context", {})
    rollback = task.get("rollbackPlan", "none")

    context_file = A2A / "tasks" / f"{task_id}-context.md"
    context_content = (
        f"# Task Brief: {task_id}\n\n"
        f"## Specification\n"
        f"- **Title:** {task.get('title', '')}\n"
        f"- **Priority:** {task.get('priority', 'normal')}\n"
        f"- **Description:** {task.get('description', '')}\n\n"
        f"## Context\n"
        + "".join(f"- {k}: {v}\n" for k, v in context.items())
        + f"- Rollback: {rollback}\n\n"
        f"## Acceptance Criteria (ALL must PASS)\n"
        + "".join(f"- {c}\n" for c in criteria)
        + f"\n## Execution Sequence\n"
        f"1. Read `.a2a/tasks/{task_id}.json` (task spec)\n"
        f"2. Read `.a2a/plans/{task_id}-plan.md` (your step-by-step instructions)\n"
        f"3. Update `{task_id}.json`: executionStartedAt=ISO now, phase=executing\n"
        f"4. Update `.a2a/status.json`: phase=executing, updatedBy=gemini\n"
        f"5. Execute every plan step — capture ALL stdout/stderr\n"
        f"6. Run ALL Verification Tests from the plan file\n"
        f"7. State PASS or FAIL with evidence for each acceptance criterion\n"
        f"8. Write `.a2a/tasks/{task_id}-feedback.json` (include criteriaResults + verificationTestResults)\n"
        f"9. Write `.a2a/feedback/{task_id}-report.md` (full narrative)\n"
        f"10. Update `{task_id}.json`: executionCompletedAt=ISO now, phase=awaiting-review\n"
        f"11. Update `.a2a/status.json`: phase=awaiting-review, updatedBy=gemini\n"
    )
    context_file.write_text(context_content, encoding="utf-8")

    # Short single-line prompt — no newlines, safe on all platforms
    prompt = (
        f"You are the Executor. "
        f"Read your role in GEMINI.md, then read .a2a/tasks/{task_id}-context.md for the full brief, "
        f"then execute {task_id} exactly as instructed. Do not invent or skip steps."
    )

    print(f"[orchestrate] Invoking Gemini for {task_id} (timeout: {args.timeout}s)...")
    print(f"[orchestrate] Working directory: {PROJECT_ROOT}")
    start = datetime.datetime.now(datetime.timezone.utc)

    # Pass prompt via env var — avoids all shell quoting issues.
    # Output goes to log file via shell redirection so Gemini keeps a real console
    # handle (required by node-pty / ConPTY on Windows).
    # We tail the log file in a thread for live display.
    import os, threading, time
    env = os.environ.copy()
    env["A2A_GEMINI_PROMPT"] = prompt
    # Disable Windows ConPTY/node-pty console attachment
    env["CI"] = "true"
    env["TERM"] = "dumb"
    env["NO_COLOR"] = "1"

    log_file.parent.mkdir(parents=True, exist_ok=True)
    log_file.write_text("", encoding="utf-8")  # truncate/create

    if sys.platform == "win32":
        # PowerShell: quote env var to prevent word-splitting,
        # use Out-File -Encoding UTF8 (not default UTF-16 LE)
        log_ps = str(log_file).replace("\\", "/")
        ps_cmd = (
            f'[Console]::OutputEncoding = [Text.Encoding]::UTF8; '
            f'gemini -p "$env:A2A_GEMINI_PROMPT" --yolo 2>&1 | '
            f"Out-File -FilePath '{log_ps}' -Encoding UTF8"
        )
        cmd = ["powershell", "-Command", ps_cmd]
    else:
        cmd = ["bash", "-c",
               f"gemini -p \"$A2A_GEMINI_PROMPT\" --yolo > {shlex.quote(str(log_file))} 2>&1"]

    try:
        process = subprocess.Popen(cmd, cwd=str(PROJECT_ROOT), env=env)
    except FileNotFoundError:
        print("[orchestrate] ERROR: 'gemini' or shell command not found.")
        print("[orchestrate] Install Gemini CLI: npm install -g @google/gemini-cli")
        sys.exit(3)

    # --- Tail log file in background thread for live output ---
    stop_tail = threading.Event()

    def tail_log():
        with open(log_file, "r", encoding="utf-8", errors="replace") as f:
            while not stop_tail.is_set():
                line = f.readline()
                if line:
                    print(line, end="", flush=True)
                else:
                    time.sleep(0.15)
            for line in f:
                print(line, end="", flush=True)

    tail_thread = threading.Thread(target=tail_log, daemon=True)
    tail_thread.start()

    # --- Wait with timeout ---
    try:
        process.wait(timeout=args.timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        stop_tail.set()
        tail_thread.join(timeout=3)
        print(f"\n[orchestrate] ERROR: Gemini timed out after {args.timeout}s.")
        print(f"[orchestrate] Partial log: {log_file}")
        sys.exit(2)

    stop_tail.set()
    tail_thread.join(timeout=5)

    elapsed = (datetime.datetime.now(datetime.timezone.utc) - start).total_seconds()

    # Read log — detect UTF-16 LE (PowerShell 5 default) and decode correctly
    raw = log_file.read_bytes()
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        full_output = raw.decode("utf-16", errors="replace")
    else:
        full_output = raw.decode("utf-8", errors="replace")

    print(f"\n[orchestrate] Gemini exited with code {process.returncode} in {elapsed:.1f}s")
    print(f"[orchestrate] Full log: {log_file}")

    # --- Check feedback files ---
    feedback_file = A2A / "tasks" / f"{task_id}-feedback.json"
    report_file = A2A / "feedback" / f"{task_id}-report.md"
    print(f"[orchestrate] Feedback JSON exists : {feedback_file.exists()} ({feedback_file})")
    print(f"[orchestrate] Report MD exists     : {report_file.exists()} ({report_file})")

    if not feedback_file.exists() or not report_file.exists():
        print("[orchestrate] WARNING: One or both feedback files were not written by Gemini.")
        print("[orchestrate] Review the log above to diagnose the issue.")

    # --- Check for escalation (needs-input) ---
    question_file = A2A / "tasks" / f"{task_id}-question.json"
    try:
        current_status = json.loads((A2A / "status.json").read_text(encoding="utf-8"))
        current_phase = current_status.get("phase", "")
    except Exception:
        current_phase = ""

    if question_file.exists() or current_phase == "needs-input":
        print(f"\n[orchestrate] ESCALATION: Gemini needs input from Claude.")
        if question_file.exists():
            q = json.loads(question_file.read_text(encoding="utf-8"))
            print(f"[orchestrate] Stuck at step: {q.get('stuckAtStep', '?')}")
            print(f"[orchestrate] Question: {q.get('question', '(no question)')}")
        print(f"[orchestrate] Claude should:")
        print(f"  1. Read .a2a/tasks/{task_id}-question.json")
        print(f"  2. Append '## Clarification' to .a2a/plans/{task_id}-plan.md")
        print(f"  3. Set phase to 'awaiting-execution'")
        print(f"  4. Re-run: python .a2a/orchestrate.py {task_id}")
        sys.exit(4)  # Special exit code for needs-input

    if process.returncode != 0:
        print(f"[orchestrate] WARNING: Gemini exited with non-zero code {process.returncode}.")
        sys.exit(process.returncode)

    print(f"[orchestrate] Done. Planner should now read the feedback files and validate.")


if __name__ == "__main__":
    main()
