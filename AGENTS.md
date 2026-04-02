# AGENTS.md — Agent Coordination Protocol
# Version: 1.0
# Agents: Claude (Planner/Orchestrator/Reviewer) + Gemini (Executor)

---

## 1. Directory Layout

All agent coordination files live under `.a2a/`:

```
.a2a/
├── tasks/
│   ├── TASK-NNN.json               <- task spec + lifecycle state (Claude writes)
│   ├── TASK-NNN-feedback.json      <- execution result (Gemini writes)
│   └── archive/                    <- completed/cancelled tasks moved here
├── plans/
│   └── TASK-NNN-plan.md            <- step-by-step plan for Gemini (Claude writes)
├── feedback/
│   └── TASK-NNN-report.md          <- full execution narrative (Gemini writes)
├── logs/
│   └── TASK-NNN-gemini.log         <- raw Gemini stdout captured by orchestrate.py
├── backups/
│   └── TASK-NNN/                   <- files backed up before Tier 3 operations
├── orchestrate.py                  <- Claude calls this to invoke Gemini
├── new-task.py                     <- creates skeleton task + plan files
├── toggle.py                       <- A2A on/off switch
├── workflow-reminder.py            <- status display hook
└── status.json                     <- single source of truth for current state
```

Task IDs are zero-padded sequential integers: TASK-001, TASK-002, etc. Never reused.

---

## 2. Task Lifecycle

```
[Claude]              [orchestrate.py]    [Gemini]           [Claude]
planning  ->  awaiting-execution  ->  executing  ->  awaiting-review  ->  approved
                                                                       -> needs-revision
                                                                       -> escalated
                                                                       -> cancelled
```

Valid `phase` values: `idle | planning | awaiting-execution | executing | needs-input | awaiting-review | approved | needs-revision | escalated | cancelled`

---

## 3. TASK-NNN.json Schema

```json
{
  "taskId": "TASK-001",
  "title": "Short human-readable title (imperative)",
  "description": "What this task accomplishes and why",
  "phase": "awaiting-execution",
  "priority": "high | normal | low",
  "createdBy": "claude",
  "createdAt": "ISO-8601 timestamp",
  "planFile": ".a2a/plans/TASK-001-plan.md",
  "context": {
    "categories": [],
    "affectedFiles": [],
    "affectedDataFiles": []
  },
  "successCriteria": [
    "Criterion 1",
    "Criterion 2"
  ],
  "rollbackPlan": "Restore from .a2a/backups/TASK-001/ if created",
  "executionStartedAt": null,
  "executionCompletedAt": null,
  "feedbackFile": ".a2a/tasks/TASK-001-feedback.json",
  "review": {
    "verdict": null,
    "reviewedAt": null,
    "notes": null,
    "nextTaskId": null
  }
}
```

---

## 4. status.json Schema

```json
{
  "protocolVersion": "1.0",
  "lastUpdated": "ISO-8601 timestamp",
  "updatedBy": "claude | gemini",
  "currentTask": "TASK-001",
  "phase": "awaiting-execution",
  "a2aEnabled": true,
  "queue": ["TASK-002"],
  "completedTasks": [],
  "notes": "Human-readable note about current state"
}
```

---

## 5. Plan File Template (TASK-NNN-plan.md)

```markdown
# Plan: TASK-NNN — [Title]
**Written by:** Claude (Planner)
**Date:** YYYY-MM-DD
**Target agent:** Gemini (Executor)

## Objective
One paragraph. What must be achieved and why.

## Pre-conditions
- [ ] Condition the Executor must verify before starting

## Steps

### Step 1 — [Name] {step-id: s1} [Tier 1]
**Working directory:** ./
**Command:**
\`\`\`bash
echo "command here"
\`\`\`
**Expected output:** Description
**On failure:** Record error, skip Step 2, continue from Step 3

## Verification Tests
Run these commands after all steps. Report exit code + output for each.

## Acceptance Criteria Checklist
- [ ] Criterion 1 -> PASS/FAIL: evidence

## Files to include in feedback
- List of files the Executor must report on
```

---

## 6. Feedback JSON Schema (TASK-NNN-feedback.json)

```json
{
  "taskId": "TASK-001",
  "executedAt": "ISO-8601 timestamp",
  "executionDurationSeconds": 142,
  "stepsCompleted": [
    {"stepId": "s1", "exitCode": 0, "durationSeconds": 30}
  ],
  "stepsFailed": [
    {"stepId": "s2", "exitCode": 1, "errorSummary": "description"}
  ],
  "stepsSkipped": [
    {"stepId": "s3", "reason": "dependent on failed s2"}
  ],
  "outputFiles": [],
  "criteriaResults": {
    "Criterion 1": {"verdict": "PASS", "evidence": "details"},
    "Criterion 2": {"verdict": "FAIL", "evidence": "details"}
  },
  "verificationTestResults": {},
  "geminiNotes": "Observations, warnings, or ambiguities"
}
```

---

## 7. Escalate-and-Resume Protocol

When Gemini gets stuck mid-execution, it can escalate to Claude for guidance:

```
[Gemini executing]  ->  stuck at step N  ->  writes question.json
                                          ->  writes partial feedback
                                          ->  sets phase="needs-input"
                                          ->  exits

[orchestrate.py]    ->  detects exit code 4 (needs-input)
                    ->  returns to Claude

[Claude]            ->  reads question.json
                    ->  analyzes the problem
                    ->  appends "## Clarification — Round N" to plan
                    ->  sets phase="awaiting-execution"
                    ->  re-invokes orchestrate.py

[Gemini re-invoked] ->  reads previous feedback (knows steps 1..N-1 done)
                    ->  reads clarification in updated plan
                    ->  resumes from step N
```

### Question File Schema (.a2a/tasks/TASK-NNN-question.json)

```json
{
  "taskId": "TASK-NNN",
  "round": 1,
  "askedAt": "ISO-8601 timestamp",
  "stuckAtStep": "s3",
  "question": "What Gemini needs from Claude",
  "context": "Findings so far that led to this question",
  "options": ["Option A considered", "Option B considered"],
  "partialFeedback": ".a2a/tasks/TASK-NNN-feedback.json"
}
```

### Clarification Section (appended to plan by Claude)

```markdown
## Clarification — Round 1
**Question from Gemini:** [copied from question.json]
**Claude's answer:** [analysis and instructions]
**Resume from:** Step s3
**Additional steps (if any):**
### Step 3a — [New step] {step-id: s3a} [Tier 1]
...
```

### Limits
- Maximum 3 escalation rounds per task. After 3, Claude must ESCALATE to human.
- Each round preserves all previous feedback and plan content.

---

## 8. Script Safety Tiers

Claude must tag every plan step with a tier. Gemini applies these rules:

| Tier | Description | Examples | Gemini Action |
|------|-------------|----------|---------------|
| **Tier 1** | Read-only | grep, validate, audit, verify | Execute freely |
| **Tier 2** | Write, reversible | New files, config updates, no deletions | Execute freely |
| **Tier 3** | Destructive or external | Deletions, API calls, git push, CI/CD | Verify backup step completed first |

---

## 9. Coordination Rules

1. Only one task may be in `executing` phase at a time.
2. Claude must check `status.json` before calling `orchestrate.py`. If phase != `awaiting-execution`, abort.
3. Gemini must not execute any task unless `phase` is `awaiting-execution`.
4. Both agents update `status.json` whenever they change the current phase.
5. If Gemini encounters ambiguity, it stops, sets phase to `awaiting-review`, and explains in the feedback.
6. **Archive rule**: on APPROVED verdict, Claude moves `TASK-NNN.json` and `TASK-NNN-feedback.json` to `.a2a/tasks/archive/`. Plans and reports stay permanently as a log.
7. Task IDs are never reused, even for cancelled tasks.

---

## 10. Quick Reference — Starting a New Task

```
You tell Claude: "Do [task description]"

Claude:
  1. python ".a2a/new-task.py" "title"      <- creates skeleton files
  2. Fills in TASK-NNN.json and plan.md
  3. Updates status.json -> awaiting-execution
  4. python ".a2a/orchestrate.py" TASK-NNN   <- invokes Gemini

Gemini (subprocess, no human action needed):
  - Reads GEMINI.md (auto-loaded) + plan file
  - Executes steps, writes feedback files
  - Updates status.json -> awaiting-review
  - Exits

Claude:
  - Reads feedback, validates against successCriteria
  - Sets verdict: APPROVED / NEEDS-REVISION / ESCALATE
  - Reports result to you
```
