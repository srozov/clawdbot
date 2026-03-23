# Session Persistence Fix: Unified Session IDs

## Problem

When using `sessions_send` to communicate with Claude Code, each invocation was spawning a **new Claude CLI session** instead of resuming the existing session. This broke conversational continuity because the context from previous messages was lost.

### Root Cause

The original implementation used two separate session ID systems:

1. **OpenClaw Session ID**: UUID stored in `~/.openclaw/agents/<agent>/sessions/sessions.json`
2. **Claude CLI Session ID**: Separate UUID generated for each CLI run

The mapping between them (`cliSessionIds` field) was stored in the session entry but was:
- Not being initialized properly for new sessions
- Being lost due to a race condition with the 45-second cache TTL

## Solution

Instead of maintaining a separate mapping layer, the OpenClaw session ID is now passed directly to Claude CLI as its session ID:

```
OpenClaw Session ID: a61712cd-0682-49c4-b2c9-77b4c5acdedc
                        ↓
Claude CLI Session ID: a61712cd-0682-49c4-b2c9-77b4c5acdedc (SAME!)
```

### Files Modified

1. **`src/agents/cli-runner/helpers.ts`**: Modified `resolveSessionIdToSend()` to use OpenClaw session ID directly
2. **`src/agents/cli-runner.ts`**: Updated calls, removed `cliSessionId` parameter
3. **`src/commands/agent.ts`**: Removed `cliSessionId` handling
4. **`src/commands/agent/session-store.ts`**: Removed `cliSessionIds` persistence
5. **`src/cron/isolated-agent/run.ts`**: Removed `cliSessionId` handling
6. **`src/auto-reply/reply/session-usage.ts`**: Removed `cliSessionId` parameter
7. **`src/auto-reply/reply/agent-runner-execution.ts`**: Removed `cliSessionId` handling

### Removed Code

- `cliSessionIds` field no longer written or read from session entries
- `claudeCliSessionId` field no longer used
- `getCliSessionId()` and `setCliSessionId()` functions are now unused (kept for reference)

## Testing Instructions

### Manual Testing with Real Telegram Sessions

1. **Clear existing sessions** (optional, for clean test):
   ```bash
   rm -f ~/.openclaw/agents/conductor/sessions/sessions.json
   rm -f ~/.openclaw/agents/conductor/sessions/*.jsonl
   ```

2. **Start a Telegram conversation with the conductor**:
   - Send a message that requires multi-turn context (e.g., "Remember this: my favorite color is blue")
   - Wait for response

3. **Check session files were created**:
   ```bash
   # OpenClaw session store should have the entry
   cat ~/.openclaw/agents/conductor/sessions/sessions.json | jq 'keys'

   # Claude CLI session file should exist
   ls -la ~/.claude/projects/-home-agi01--openclaw-workspace-claude-code/*.jsonl
   ```

4. **Continue the conversation**:
   - Send a follow-up message (e.g., "What color did I say I liked?")
   - The response should show the Claude CLI is resuming the session

5. **Verify session persistence**:
   ```bash
   # Check that Claude CLI session file has grown
   wc -l ~/.claude/projects/-home-agi01--openclaw-workspace-claude-code/*.jsonl

   # Check OpenClaw session entry has the correct CLI session ID
   cat ~/.openclaw/agents/conductor/sessions/sessions.json | jq '."agent:conductor:telegram:group:-1003745187814:topic:492" | {sessionId, cliSessionIds}'
   ```

### Automated Testing Checklist

- [ ] First `sessions_send` creates both OpenClaw and Claude CLI session files with the same ID
- [ ] Second `sessions_send` reuses the existing Claude CLI session (no new file created)
- [ ] Claude CLI session file accumulates messages across calls
- [ ] Claude CLI respects `--resume <sessionId>` and continues conversation
- [ ] Session context is preserved (can reference earlier messages)

### Debug Commands

```bash
# Watch for Claude CLI session creation
ls -la ~/.claude/projects/-home-agi01--openclaw-workspace-claude-code/*.jsonl | tail -f

# Check OpenClaw session store in real-time
cat ~/.openclaw/agents/conductor/sessions/sessions.json | jq

# Tail conductor logs (if logging configured)
tail -f ~/.openclaw/logs/conductor/*.log
```

## Compatibility

- **No backwards compatibility**: The `cliSessionIds` and `claudeCliSessionId` fields are no longer used or written
- **Claude CLI**: Uses `--session-id <OpenClawSessionId>` to set session
- **No changes to user-facing behavior**: This is an internal infrastructure fix
