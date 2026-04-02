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
import os
import threading
import time

PROJECT_ROOT = pathlib.Path(__file__).parent.parent
A2A = PROJECT_ROOT / ".a2a"


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def main():
    parser = argparse.ArgumentParser(description="Invoke Gemini CLI on a task.")
    parser.add_argument("task_id", help="Task ID, e.g. TASK-001")
    parser.add_argument("--timeout", type=int, default=600,
                        help="Max seconds to wait for Gemini (default: 600)")
    parser.add_argument("--model", type=str, default=None,
                        help="Override executor model (e.g. gemini-2.5-pro, gemini-2.5-flash)")
    args = parser.parse_args()

    task_id = args.task_id
    task_file = A2A / "tasks" / f"{task_id}.json"
    plan_file = A2A / "plans" / f"{task_id}-plan.md"
    log_file = A2A / "logs" / f"{task_id}-gemini.log"
    feedback_file = A2A / "tasks" / f"{task_id}-feedback.json"
    question_file = A2A / "tasks" / f"{task_id}-question.json"
    log_file.parent.mkdir(parents=True, exist_ok=True)

    # --- Pre-condition checks ---
    if not task_file.exists():
        print(f"[orchestrate] ERROR: {task_file} not found.")
        sys.exit(1)
    if not plan_file.exists():
        print(f"[orchestrate] ERROR: {plan_file} not found.")
        sys.exit(1)

    task = json.loads(task_file.read_text(encoding="utf-8"))
    if task.get("phase") != "awaiting-execution":
        print(f"[orchestrate] ERROR: phase='{task.get('phase')}', expected 'awaiting-execution'.")
        sys.exit(1)

    criteria = task.get("successCriteria", [])

    # --- Resolve executor model ---
    # Priority: CLI --model flag > task JSON executorModel > status.json defaultModel > none
    model = args.model
    if not model:
        model = task.get("executorModel")
    if not model:
        try:
            st = json.loads((A2A / "status.json").read_text(encoding="utf-8"))
            model = st.get("defaultModel")
        except Exception:
            pass

    if model:
        print(f"[orchestrate] Model: {model}")

    # --- Count iteration (for token-efficient delta context) ---
    iteration = 1
    existing_logs = sorted(A2A.glob(f"logs/{task_id}-gemini*.log"))
    if existing_logs:
        iteration = len(existing_logs) + 1
    # Rename current log to include iteration number on re-runs
    if iteration > 1:
        log_file = A2A / "logs" / f"{task_id}-gemini-r{iteration}.log"

    # --- Detect resume mode ---
    is_resume = feedback_file.exists() and question_file.exists()

    # --- Build token-efficient feedback instruction ---
    # On iterations > 1, tell Gemini to write delta feedback (only failures + changes)
    feedback_hint = ""
    if iteration > 1:
        feedback_hint = (
            f"\n## Feedback Optimization (iteration {iteration})\n"
            f"This is re-run #{iteration}. In your feedback:\n"
            f"- Only include full stdout for FAILED steps\n"
            f"- For passing steps, write: stepId + 'PASS' + 1-line summary\n"
            f"- Focus report on what CHANGED vs previous run\n"
        )

    if is_resume:
        prev = json.loads(feedback_file.read_text(encoding="utf-8"))
        completed = [s["stepId"] for s in prev.get("stepsCompleted", [])]
        q = json.loads(question_file.read_text(encoding="utf-8"))
        stuck_at = q.get("stuckAtStep", "?")

        context_content = (
            f"# Task Brief: {task_id} (RESUMING — round {iteration})\n\n"
            f"Task spec: `.a2a/tasks/{task_id}.json`\n"
            f"Plan: `.a2a/plans/{task_id}-plan.md`\n\n"
            f"## Resume Brief\n"
            f"- Steps done: {', '.join(completed)}\n"
            f"- Stuck at: {stuck_at}\n"
            f"- Read `## Clarification` in plan for Claude's answer\n"
            f"- Skip completed steps, resume from {stuck_at}\n"
            + feedback_hint
            + f"\n## Acceptance Criteria\n"
            + "".join(f"- {c}\n" for c in criteria)
        )
        prompt = (
            f"You are resuming {task_id}. "
            f"Read .a2a/tasks/{task_id}-context.md for the resume brief, "
            f"then read the updated plan. Skip completed steps, resume execution."
        )
    else:
        context_content = (
            f"# Task Brief: {task_id}\n\n"
            f"Task spec: `.a2a/tasks/{task_id}.json`\n"
            f"Plan: `.a2a/plans/{task_id}-plan.md`\n\n"
            f"## Your Sequence\n"
            f"1. Read task JSON + plan file\n"
            f"2. Set phase=executing, execute all plan steps, capture output\n"
            f"3. Write feedback JSON + report MD\n"
            f"4. Set phase=awaiting-review\n"
            + feedback_hint
            + f"\n## Acceptance Criteria\n"
            + "".join(f"- {c}\n" for c in criteria)
        )
        prompt = (
            f"You are the Executor. "
            f"Read your role in GEMINI.md, then read .a2a/tasks/{task_id}-context.md, "
            f"then execute {task_id} exactly as instructed."
        )

    # Write context file
    context_file = A2A / "tasks" / f"{task_id}-context.md"
    context_file.write_text(context_content, encoding="utf-8")

    print(f"[orchestrate] {'Resuming' if is_resume else 'Invoking'} Gemini for {task_id} (timeout: {args.timeout}s)")
    start = datetime.datetime.now(datetime.timezone.utc)

    # --- Environment setup ---
    env = os.environ.copy()
    env["A2A_GEMINI_PROMPT"] = prompt
    env["CI"] = "true"       # Disable ConPTY/node-pty
    env["TERM"] = "dumb"
    env["NO_COLOR"] = "1"

    log_file.write_text("", encoding="utf-8")  # truncate

    # --- Direct subprocess (no PowerShell wrapper) ---
    # Write to log file directly via file descriptor to avoid shell overhead
    # and UTF-16 encoding issues on Windows.
    log_fd = open(log_file, "w", encoding="utf-8", errors="replace")

    try:
        model_flag = f" --model {model}" if model else ""
        if sys.platform == "win32":
            cmd = ["cmd", "/c",
                   f'gemini -p "%A2A_GEMINI_PROMPT%" --yolo{model_flag}']
        else:
            cmd = ["bash", "-c",
                   f'gemini -p "$A2A_GEMINI_PROMPT" --yolo{model_flag}']

        process = subprocess.Popen(
            cmd, cwd=str(PROJECT_ROOT), env=env,
            stdout=log_fd, stderr=subprocess.STDOUT
        )
    except FileNotFoundError:
        log_fd.close()
        print("[orchestrate] ERROR: 'gemini' command not found.")
        print("[orchestrate] Install: npm install -g @google/gemini-cli")
        sys.exit(3)

    # --- Tail log for live output ---
    stop_tail = threading.Event()

    def tail_log():
        with open(log_file, "r", encoding="utf-8", errors="replace") as f:
            while not stop_tail.is_set():
                line = f.readline()
                if line:
                    print(line, end="", flush=True)
                else:
                    time.sleep(0.05)  # 50ms (was 150ms)
            for line in f:
                print(line, end="", flush=True)

    tail_thread = threading.Thread(target=tail_log, daemon=True)
    tail_thread.start()

    # --- Wait ---
    try:
        process.wait(timeout=args.timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        stop_tail.set()
        tail_thread.join(timeout=3)
        log_fd.close()
        print(f"\n[orchestrate] TIMEOUT after {args.timeout}s. Log: {log_file}")
        sys.exit(2)

    stop_tail.set()
    tail_thread.join(timeout=5)
    log_fd.close()

    elapsed = (datetime.datetime.now(datetime.timezone.utc) - start).total_seconds()
    print(f"\n[orchestrate] Gemini exited code {process.returncode} in {elapsed:.1f}s")

    # --- Check for escalation (needs-input) ---
    try:
        cur_status = json.loads((A2A / "status.json").read_text(encoding="utf-8"))
        cur_phase = cur_status.get("phase", "")
    except Exception:
        cur_phase = ""

    q_exists = (A2A / "tasks" / f"{task_id}-question.json").exists()
    if q_exists or cur_phase == "needs-input":
        print(f"\n[orchestrate] ESCALATION: Gemini needs input from Claude.")
        if q_exists:
            q = json.loads((A2A / "tasks" / f"{task_id}-question.json").read_text(encoding="utf-8"))
            print(f"  Stuck at: {q.get('stuckAtStep', '?')}")
            print(f"  Question: {q.get('question', '(none)')}")
        print(f"  -> Claude: read question, append Clarification to plan, re-invoke")
        sys.exit(4)

    # --- Check feedback files ---
    report_file = A2A / "feedback" / f"{task_id}-report.md"
    fb_ok = feedback_file.exists()
    rpt_ok = report_file.exists()
    print(f"[orchestrate] Feedback: {fb_ok} | Report: {rpt_ok}")

    if not fb_ok or not rpt_ok:
        print("[orchestrate] WARNING: Feedback files missing. Check log.")

    if process.returncode != 0:
        print(f"[orchestrate] WARNING: exit code {process.returncode}")
        sys.exit(process.returncode)

    print("[orchestrate] Done. Planner should review feedback.")


if __name__ == "__main__":
    main()
