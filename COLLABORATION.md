# COLLABORATION.md — OpenClaw Multi-Agent Framework

How agents share work without stepping on each other. Every agent should read this
at session start. It defines two things: **where files go**, and **who does what**.

---


## The Two Zones

Every file belongs to one of two zones. Getting this wrong is the #1 source of mess.

### Zone 1 — Agent Memory (`workspace-<name>/`)

Private. Only the owning agent reads and writes here. This is state that persists
*for that agent* across sessions. Nothing else.

| File | Purpose |
|---|---|
| `IDENTITY.md` | Name, vibe, avatar |
| `SOUL.md` | Behavioral rules for this agent |
| `MEMORY.md` | What this agent remembers between sessions |
| `USER.md` | Notes about the user |
| `HEARTBEAT.md` | Liveness signal (system-managed) |
| `AGENTS.md` | Agent roster (system-managed, read-only) |
| `TOOLS.md` | Available tools |
| `PROJECTS.md` | This agent's role and project list |

Agent-specific *input data* also lives here. Example: Trader's IBKR portfolio exports
go in `workspace-trader/data/` because only Trader consumes them.

**Agent-specific skills** also live here:
- `workspace-career-coach/skills/` → career-coach's migrated tools
- `workspace-trader/skills/` → trader's migrated tools

**Nothing else.** If another agent needs to read it, it does not belong here.

---


## Project Repos

Projects are standalone repositories. All agents access them via symlinks.

| Project | Canonical path | Agents |
|---|---|---|
| job-application-agency | `/home/agi01/job-application-agency/` | conductor, career-coach |
| stock-picking-agency | `/home/agi01/stock-picking-agency/` | conductor, trader |

---


## The Symlink Convention

Project repos live outside all workspaces. All agents access projects via symlinks:

```
workspace-career-coach/job-application-agency → /home/agi01/job-application-agency
workspace-trader/stock-picking-agency          → /home/agi01/stock-picking-agency
```

**Symlinks are read-write.** Writing through a symlink writes to the canonical repo.

---


## Agent Responsibilities

### Main
- Entry point. User messages land here first.
- Routes project work to Conductor. Does not touch project dirs directly.

### Conductor
- Orchestrates all projects. Owns `CONTEXT.md` in each project dir.
- Updates CONTEXT.md when: spawning agents, milestones complete, blockers surface.
- Spawns Claude Code for implementation tasks.
- Spawns domain agents for requirements/validation.
- Commits changes after Claude Code finishes.

### Claude Code
- Full implementation agent. Works in project repos.
- Receives tasks from Conductor, implements, returns results.
- Does not own project context — Conductor owns CONTEXT.md.

### Career Coach (job-application-agency only)
- Defines requirements → Claude Code implements → Career Coach tests.
- Test results and requirements docs go in the project dir.
- Owns migrated skills in `workspace-career-coach/skills/`.

### Trader (stock-picking-agency only)
- Research and portfolio validation.
- IBKR data and portfolio exports stay in `workspace-trader/data/` (agent-specific input).
- Research outputs and valuation results go in the project dir.
- Owns migrated skills in `workspace-trader/skills/`.

### KB
- Knowledge archive. Serves both projects.
- Stores and retrieves from `workspace-kb/vault/`.
- Does not write to project dirs.

---


## Spawn Hierarchy

```
Main
 └─ Conductor
      ├─ Claude Code
      ├─ Career Coach
      ├─ Trader
      └─ KB
```

Matches `openclaw.json` `subagents.allowAgents`. If an agent isn't in your allow list,
you can't spawn it — route through Conductor.

---


## Rules

1. **Project code goes in project repos.** Implementation, configs, tests —
    everything lives in `/home/agi01/<project>/`.
2. **Agent-specific skills go in agent workspace.** `workspace-<name>/skills/`.
3. **Read `CONTEXT.md` before touching a project.** Every agent. Every session.
4. **Only Conductor writes `CONTEXT.md`.** Other agents update Conductor, who updates it.
5. **Agent-specific input data stays in the agent workspace.** Trader's portfolio XMLs,
    Career Coach's draft notes — stuff only that agent uses.
6. **Don't leave artifacts in workspace root.** No `TASK1_COMPLETE.md`, no
    `STATUS_REPORT.md` in `workspace-*/`. Those go in the project dir or get deleted.
7. **BOOTSTRAP.md is a one-time script.** Delete it after first session. It should not
    persist.
