# Claude + Gemini A2A Framework

A file-based **Agent-to-Agent (A2A)** orchestration framework where **Claude Code** (Planner/Orchestrator/Reviewer) delegates tasks to **Gemini CLI** (Executor/Investigator) — fully autonomous, no human intervention needed during execution.

## How It Works

```
You tell Claude: "Do [task]"

Claude:                           Gemini (subprocess):
  1. Creates task + plan            5. Reads plan
  2. Sets criteria                  6. Executes steps
  3. Invokes orchestrate.py  ────>  7. Writes feedback
  4. Waits...               <────  8. Updates status

Claude:                           If Gemini gets stuck:
  9. Reads feedback                 7b. Writes question.json
  10. Validates criteria            7c. Exits with "needs-input"
  11. APPROVED / REVISION /         Claude reads question, appends
      ESCALATE                      clarification to plan, re-invokes
```

## Quick Start

### Prerequisites

- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) installed and authenticated
- [Gemini CLI](https://github.com/google-gemini/gemini-cli) installed (`npm install -g @google/gemini-cli`) and authenticated
- Python 3.8+

### Installation

```bash
# Clone the repo
git clone https://github.com/GabrAGM/claude-gemini-a2a.git

# Run the setup script from your project root
cd your-project
python path/to/claude-gemini-a2a/setup.py
```

The setup script will:
1. Create the `.a2a/` directory structure in your project
2. Copy all framework scripts
3. Generate `CLAUDE.md`, `GEMINI.md`, and `AGENTS.md` tailored to your project
4. Configure Claude Code hooks and slash commands
5. Initialize `status.json`

### Manual Installation

If you prefer manual setup, copy these into your project root:

```
your-project/
├── .a2a/
│   ├── orchestrate.py          # Invokes Gemini on a task
│   ├── new-task.py             # Creates task skeletons
│   ├── toggle.py               # A2A on/off switch
│   ├── workflow-reminder.py    # Status display hook
│   ├── status.json             # State tracking
│   ├── tasks/
│   │   └── archive/
│   ├── plans/
│   ├── feedback/
│   ├── logs/
│   └── backups/
├── .claude/
│   ├── settings.local.json     # Hook configuration
│   └── commands/               # Slash commands
│       ├── a2a-on.md
│       ├── a2a-off.md
│       ├── a2a-status.md
│       ├── hook-on.md
│       └── hook-off.md
├── CLAUDE.md                   # Planner role instructions
├── GEMINI.md                   # Executor role instructions
└── AGENTS.md                   # Shared protocol
```

## Usage

### Enable/Disable A2A

```bash
python .a2a/toggle.py on    # Claude delegates to Gemini
python .a2a/toggle.py off   # Claude works directly
python .a2a/toggle.py       # Check current mode
```

Or use Claude Code slash commands: `/a2a-on`, `/a2a-off`, `/a2a-status`

### Delegation Modes

Claude automatically selects one of three modes for every request:

| Mode | When | What Happens |
|------|------|-------------|
| **DIRECT** | Simple questions, single-file reads | Claude handles it alone |
| **INVESTIGATE** | Bug diagnosis, multi-file search | Gemini explores, Claude concludes |
| **EXECUTE** | Code changes, multi-step ops | Gemini runs, Claude reviews |

### Task Lifecycle

```
idle → planning → awaiting-execution → executing → awaiting-review → approved
                        ↑                  ↓                        ↘ needs-revision
                        └── needs-input ←──┘                        ↘ escalated
                        (Gemini asks Claude for help,
                         Claude answers, re-invokes)
```

### Escalate-and-Resume

When Gemini hits a blocker during execution, it can **ask Claude for help**:

1. Gemini writes a question file with context about what it's stuck on
2. Gemini exits cleanly with partial progress saved
3. Claude reads the question, analyzes the problem
4. Claude appends a `## Clarification` section to the plan with the answer
5. Claude re-invokes Gemini, which skips completed steps and resumes

This enables **active collaboration** between the agents — up to 3 rounds per task.

### Model Selection

Choose the right Gemini model per task:

```bash
# Per invocation
python .a2a/orchestrate.py TASK-001 --model gemini-2.5-pro

# Per task (in TASK-NNN.json)
"executorModel": "gemini-2.5-flash"

# Global default (in status.json)
"defaultModel": "gemini-2.5-flash"
```

| Task Type | Recommended Model |
|-----------|-------------------|
| Simple file ops, validation | `gemini-2.5-flash` |
| Complex multi-step code changes | `gemini-2.5-pro` |
| Visual/screenshot tasks | `gemini-2.5-flash-preview-image` |
| Large codebase investigation | `gemini-2.5-pro` |

Priority: `--model` flag > task `executorModel` > `defaultModel` > Gemini CLI default.

### Risk Tiers

Every plan step is tagged with a safety tier:

| Tier | Type | Examples | Rule |
|------|------|----------|------|
| 1 | Read-only | Grep, validate, audit | Execute freely |
| 2 | Write, reversible | Create files, update configs | Execute freely |
| 3 | Destructive/external | Delete, API calls, git push | Backup first |

## Architecture

### File-Based Protocol

No HTTP servers, no message queues — just files:

- **`status.json`** — Single source of truth (phase, current task, queue)
- **`TASK-NNN.json`** — Task specification with criteria
- **`TASK-NNN-plan.md`** — Step-by-step execution instructions
- **`TASK-NNN-feedback.json`** — Structured execution results
- **`TASK-NNN-report.md`** — Human-readable execution narrative

### Key Design Decisions

1. **Gemini runs headless** via `gemini -p "prompt" --yolo` (auto-approves tool calls)
2. **Prompt passed via env var** to avoid shell quoting issues on Windows
3. **Output captured to log file** (not piped) to avoid node-pty/ConPTY issues
4. **Context written to file** — Gemini reads task details from `.a2a/tasks/TASK-NNN-context.md`
5. **Absolute prohibitions** — Gemini cannot create tasks, modify plans, or manage task lifecycle

### Token Optimization

The framework is designed to minimize token consumption:

- **GEMINI.md is minimal** (~35 lines) — only behavioral rules, no duplicated sequences
- **Context file is smart** — references task JSON instead of copying it; adds resume brief on re-invocation
- **Single source of truth** — schemas in AGENTS.md only, no duplication across files
- **Compact status hook** — 1-line output instead of 45-line mode descriptions
- **Direct subprocess** — cmd.exe on Windows (no PowerShell startup overhead)
- **Delta feedback on iterations** — re-runs only report failures in detail, passing steps get 1-line summaries
- **Progressive logging** — each iteration preserved separately (`TASK-001-gemini-r2.log`)
- **Model switching** — use fast models for simple tasks, pro models for complex ones

## Customization

### Adding Your Own Context Fields

Edit the `context` object in `TASK-NNN.json`:

```json
"context": {
  "categories": ["your-domain-categories"],
  "operationTypes": ["your-operation-types"],
  "affectedScripts": ["path/to/scripts"],
  "affectedDataFiles": ["path/to/data"]
}
```

### Changing the Executor

To use a different executor agent (not Gemini CLI), modify `orchestrate.py`:

1. Change the subprocess command (line ~142)
2. Update environment variable handling
3. Adjust log file parsing if needed

## Troubleshooting

### AttachConsole Failed (Windows)

Gemini CLI uses node-pty which requires a console. The framework sets `CI=true`, `TERM=dumb`, `NO_COLOR=1` to mitigate this, but shell commands may still fail. Gemini can use its file-reading tools as a fallback.

### Gemini Settings Warning

If you see `"model": Expected object, received string`, update `~/.gemini/settings.json`:
```json
{
  "model": { "name": "models/gemini-2.0-flash" }
}
```

### Task Stuck in "executing"

Reset manually:
```bash
python -c "
import json
s = json.load(open('.a2a/status.json'))
s['phase'] = 'idle'
s['currentTask'] = None
json.dump(s, open('.a2a/status.json', 'w'), indent=2)
print('Reset to idle')
"
```

## License

MIT
