---
name: coding-agent
description: Run Codex CLI, Claude Code, OpenCode, or Pi Coding Agent via background process for programmatic control.
metadata: {"openclaw":{"emoji":"🧩","requires":{"anyBins":["claude","codex","opencode","pi"]}}}
---

# Coding Agent

**Note for Claude Code:** For Claude Code, the **OpenClaw CLI backend** is the preferred integration. Use `openclaw agent --message "..." --model claude-cli/opus` instead of this skill for structured plan→execute workflows. This skill is useful for Codex, OpenCode, Pi, or advanced Claude Code use cases (background sessions, custom PTY handling).

## Claude Code via CLI Backend (Recommended for Plan→Execute)

For Claude Code, use OpenClaw's native CLI backend:

```bash
openclaw agent --message "<task>" --model claude-cli/opus
```

This provides:
- Plan mode (`--permission-mode plan`) for read-only planning
- Execute mode (`--permission-mode auto`) for full implementation
- Automatic session management
- JSON output parsing

## Claude Code via PTY (Legacy/Bash)

For advanced use cases, use **bash** with `pty:true`:

```bash
# ✅ Correct - with PTY
bash pty:true workdir:/home/agi01/<project> command:"claude -p '<task>'"

# ❌ Wrong - no PTY, agent may break
bash command:"claude -p '<task>'"
```

### Bash Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `command` | string | Shell command to run |
| `pty` | boolean | **Required for coding agents** |
| `workdir` | string | Agent sees only this directory |
| `background` | boolean | Run in background, returns sessionId |
| `timeout` | number | Timeout in seconds |
| `elevated` | boolean | Run on host (if allowed) |

### Process Actions (for background sessions)

| Action | Description |
|--------|-------------|
| `list` | List running/recent sessions |
| `poll` | Check if session is running |
| `log` | Get session output |
| `write` | Send raw data to stdin |
| `submit` | Send data + newline |
| `send-keys` | Send key tokens |
| `paste` | Paste text with optional bracketed mode |
| `kill` | Terminate session |

---

## Claude Code (Recommended)

Claude Code is the **primary implementation agent**. It is a **tool**, not a peer agent. You own the session, review plans, and commit results.

### Workflow Overview

```
Spawn plan mode → Review plan → Approve/correct → Agent implements → You commit
```

### 1. Spawn Plan Mode

```bash
bash pty:true background:true workdir:/home/agi01/<project> command:"claude --permission-mode plan '<task description>'"
```

Returns: `{"sessionId":"<id>", ...}`

**Store the sessionId in your context.** You own this session.

### 2. Review Plan

```bash
read path:~/.claude/sessions/<sessionId>.jsonl
```

Read the session transcript to review the plan.

### 3. Submit Corrections or Approve

```bash
bash pty:true background:true command:"claude --session-id <sessionId> --permission-mode auto '<corrections or proceed>'"
```

| Mode | Effect |
|------|--------|
| `--permission-mode plan` | Read-only, cannot modify files |
| `--permission-mode auto` | Can read/edit within workdir |
| `--permission-mode all` | Full machine access |

### 4. Monitor Execution

```bash
read path:~/.claude/sessions/<sessionId>.jsonl
```

Can interject mid-execution:
```bash
bash command:"claude --session-id <sessionId> '<interjection>'"
```

### 5. Review Changes

```bash
bash command:"git diff --stat" workdir:/home/agi01/<project>
bash command:"git diff" workdir:/home/agi01/<project>
```

### 6. Commit Manually

```bash
bash command:"git add . && git commit -m '<message>'" workdir:/home/agi01/<project>
```

**Claude Code cannot commit** — you review and commit.

### Session Management

| Action | Command |
|--------|---------|
| List sessions | `ls ~/.claude/sessions/` |
| Read transcript | `read path:~/.claude/sessions/<sessionId>.jsonl` |
| Resume session | `claude --session-id <id> '<instructions>'` |
| Kill session | `bash command:"pkill -f 'claude.*session-id <sessionId>'"` |

### One-Shot (No Plan Mode)

```bash
bash pty:true workdir:/home/agi01/<project> command:"claude -p '<task>'"
```

### Model Selection

```bash
--model sonnet    # Claude Sonnet 4 (default)
--model opus      # Claude Opus 4 (stronger reasoning)
```

---

## Codex CLI

**Note:** Codex does not have programmatic plan mode. Plan→approve→execute requires the TUI.

### Quick Start

```bash
# Codex needs a git repo!
cd /home/agi01/<project>
codex exec "Your prompt"
```

### Flags

| Flag | Effect |
|------|--------|
| `exec "prompt"` | One-shot execution, exits when done |
| `--full-auto` | Sandboxed + auto-approves |
| `--yolo` | No sandbox + no approvals |

### Background Mode

```bash
bash pty:true workdir:/home/agi01/<project> background:true command:"codex exec --full-auto '<task>'"
# Returns sessionId
process action:log sessionId:XXX
```

### Resume Session

```bash
codex exec resume --last "Continue task"
codex exec resume <SESSION_ID> "Continue task"
```

### PR Review (TUI Only)

```bash
codex review --base main
```

---

## OpenCode

```bash
bash pty:true workdir:/home/agi01/<project> command:"opencode run '<task>'"
```

### Session Management

```bash
opencode session list           # List sessions
opencode export <sessionId>     # Export transcript
opencode --session <id>         # Resume session
```

### Flags

| Flag | Effect |
|------|--------|
| `--model provider/model` | Specify model |
| `--continue` | Continue last session |
| `--session <id>` | Resume specific session |

---

## Pi Coding Agent

```bash
# Install: npm install -g @mariozechner/pi-coding-agent
bash pty:true workdir:/home/agi01/<project> command:"pi '<task>'"
```

### Flags

| Flag | Effect |
|------|--------|
| `-p "prompt"` | Non-interactive mode |
| `--provider openai` | Switch provider |
| `--model gpt-4o-mini` | Switch model |

---

## Parallel Worktrees (Codex/Pi)

```bash
# Create worktrees for parallel fixes
git worktree add -b fix/issue-78 /tmp/issue-78 main
git worktree add -b fix/issue-99 /tmp/issue-99 main

# Launch agents
bash pty:true workdir:/tmp/issue-78 background:true command:"codex --yolo 'Fix issue #78'"
bash pty:true workdir:/tmp/issue-99 background:true command:"pi 'Fix issue #99'"

# Monitor
process action:list

# Commit and cleanup
bash command:"git add . && git commit -m 'fix: ...'" workdir:/tmp/issue-78
git worktree remove /tmp/issue-78
git worktree remove /tmp/issue-99
```

---

## Rules

1. **Always use pty:true** - coding agents need terminals
2. **Claude Code is primary tool** - accurate plan mode, good session management
3. **You own the sessionId** - it's yours until you kill it
4. **Claude Code cannot commit** - review and commit manually
5. **Read session transcripts** - `~/.claude/sessions/*.jsonl` is source of truth
6. **Workdir matters** - set correct project path
7. **Codex has no programmatic plan mode** - use Claude Code for plan→approve→execute
8. **Don't leave artifacts** - clean up after sessions

---

## Progress Updates

Keep the user in the loop:

- Send 1 message when starting (what + where)
- Update when:
  - Milestone completes
  - Agent asks for input
  - Error occurs
  - Agent finishes (include what changed)
- If you kill a session, say why

---

## Example: Implement Feature with Claude Code

```bash
# 1. Spawn in plan mode
bash pty:true background:true workdir:/home/agi01/job-application-agency command:"claude --permission-mode plan 'Add memory_write function to store session context. Include error handling.'"

# 2. Review plan (extract sessionId)
read path:~/.claude/sessions/abc123.jsonl

# 3. Approve with corrections
bash pty:true background:true command:"claude --session-id abc123 --permission-mode auto 'Good plan. Also add unit tests in tests/ directory.'"

# 4. Wait for completion, review changes
bash command:"git diff --stat" workdir:/home/agi01/job-application-agency
bash command:"git diff" workdir:/home/agi01/job-application-agency

# 5. Commit
bash command:"git add . && git commit -m 'feat: add memory_write function with tests'" workdir:/home/agi01/job-application-agency

# 6. Optional: cleanup
bash command:"pkill -f 'claude.*session-id abc123'"
```

---

## Troubleshooting

**Session not responding:**
```bash
read path:~/.claude/sessions/<sessionId>.jsonl
```

**Permission denied (Claude Code):**
```bash
which claude
claude auth status
```

**Process hung:**
```bash
pkill -f claude    # Claude Code
pkill -f codex    # Codex
```

---

## Reference

- `COLLABORATION.md` → Policy reference (when/why to use CLI agents). Path: `/home/agi01/clawdbot/COLLABORATION.md`
- This skill → Technical reference (exact commands)
