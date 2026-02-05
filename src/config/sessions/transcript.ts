import fs from "node:fs";
import path from "node:path";

import { CURRENT_SESSION_VERSION, SessionManager } from "@mariozechner/pi-coding-agent";

import type { SessionEntry } from "./types.js";
import { loadSessionStore, updateSessionStore } from "./store.js";
import { resolveDefaultSessionStorePath, resolveSessionTranscriptPath } from "./paths.js";
import { emitSessionTranscriptUpdate } from "../../sessions/transcript-events.js";

/**
 * Extract threadId from a session key.
 * Supports both `:topic:` and `:thread:` suffixes.
 * Returns undefined if no thread/topic suffix is found.
 */
function extractThreadIdFromSessionKey(sessionKey: string): string | undefined {
  // Try :topic: format first (Telegram)
  const topicMatch = sessionKey.match(/:topic:(\d+)$/);
  if (topicMatch) return topicMatch[1];

  // Try :thread: format (other platforms)
  const threadMatch = sessionKey.match(/:thread:(\d+)$/);
  if (threadMatch) return threadMatch[1];

  return undefined;
}

function stripQuery(value: string): string {
  const noHash = value.split("#")[0] ?? value;
  return noHash.split("?")[0] ?? noHash;
}

function extractFileNameFromMediaUrl(value: string): string | null {
  const trimmed = value.trim();
  if (!trimmed) return null;
  const cleaned = stripQuery(trimmed);
  try {
    const parsed = new URL(cleaned);
    const base = path.basename(parsed.pathname);
    if (!base) return null;
    try {
      return decodeURIComponent(base);
    } catch {
      return base;
    }
  } catch {
    const base = path.basename(cleaned);
    if (!base || base === "/" || base === ".") return null;
    return base;
  }
}

export function resolveMirroredTranscriptText(params: {
  text?: string;
  mediaUrls?: string[];
}): string | null {
  const mediaUrls = params.mediaUrls?.filter((url) => url && url.trim()) ?? [];
  if (mediaUrls.length > 0) {
    const names = mediaUrls
      .map((url) => extractFileNameFromMediaUrl(url))
      .filter((name): name is string => Boolean(name && name.trim()));
    if (names.length > 0) return names.join(", ");
    return "media";
  }

  const text = params.text ?? "";
  const trimmed = text.trim();
  return trimmed ? trimmed : null;
}

async function ensureSessionHeader(params: {
  sessionFile: string;
  sessionId: string;
}): Promise<void> {
  if (fs.existsSync(params.sessionFile)) return;
  await fs.promises.mkdir(path.dirname(params.sessionFile), { recursive: true });
  const header = {
    type: "session",
    version: CURRENT_SESSION_VERSION,
    id: params.sessionId,
    timestamp: new Date().toISOString(),
    cwd: process.cwd(),
  };
  await fs.promises.writeFile(params.sessionFile, `${JSON.stringify(header)}\n`, "utf-8");
}

export async function appendAssistantMessageToSessionTranscript(params: {
  agentId?: string;
  sessionKey: string;
  text?: string;
  mediaUrls?: string[];
  /** Optional override for store path (mostly for tests). */
  storePath?: string;
}): Promise<{ ok: true; sessionFile: string } | { ok: false; reason: string }> {
  const sessionKey = params.sessionKey.trim();
  if (!sessionKey) return { ok: false, reason: "missing sessionKey" };

  const mirrorText = resolveMirroredTranscriptText({
    text: params.text,
    mediaUrls: params.mediaUrls,
  });
  if (!mirrorText) return { ok: false, reason: "empty text" };

  const storePath = params.storePath ?? resolveDefaultSessionStorePath(params.agentId);
  const store = loadSessionStore(storePath, { skipCache: true });
  const entry = store[sessionKey] as SessionEntry | undefined;
  if (!entry?.sessionId) {
    console.error("[transcript] Session entry not found:", {
      sessionKey,
      agentId: params.agentId,
      storeKeys: Object.keys(store),
    });
    return { ok: false, reason: `unknown sessionKey: ${sessionKey}` };
  }

  // For topic sessions, the sessionFile may not be set correctly (gateway may set it to the
  // main transcript path). Always extract threadId from the session key and use it to
  // resolve the correct transcript path.
  const threadId =
    extractThreadIdFromSessionKey(sessionKey) ??
    entry.deliveryContext?.threadId ??
    entry.lastThreadId;
  // Always resolve the correct path based on threadId, even if sessionFile is already set
  const resolvedSessionFile = resolveSessionTranscriptPath(
    entry.sessionId,
    params.agentId,
    threadId,
  );

  console.error("[transcript] Writing A2A context:", {
    sessionKey,
    threadId,
    resolvedSessionFile,
    oldSessionFile: entry.sessionFile,
  });

  await ensureSessionHeader({ sessionFile: resolvedSessionFile, sessionId: entry.sessionId });

  const sessionManager = SessionManager.open(resolvedSessionFile);
  sessionManager.appendMessage({
    role: "assistant",
    content: [{ type: "text", text: mirrorText }],
    api: "openai-responses",
    provider: "openclaw",
    model: "delivery-mirror",
    usage: {
      input: 0,
      output: 0,
      cacheRead: 0,
      cacheWrite: 0,
      totalTokens: 0,
      cost: {
        input: 0,
        output: 0,
        cacheRead: 0,
        cacheWrite: 0,
        total: 0,
      },
    },
    stopReason: "stop",
    timestamp: Date.now(),
  });

  if (!entry.sessionFile || entry.sessionFile !== resolvedSessionFile) {
    await updateSessionStore(storePath, (current) => {
      current[sessionKey] = {
        ...entry,
        sessionFile: resolvedSessionFile,
      };
    });
  }

  emitSessionTranscriptUpdate(resolvedSessionFile);
  return { ok: true, sessionFile: resolvedSessionFile };
}

/**
 * Persist both user prompt and assistant response for a CLI backend run.
 * Called after `runCliAgent()` completes so the session JSONL transcript
 * contains the full conversation (visible in web UI and `sessions_history`).
 */
export async function appendCliRunToSessionTranscript(params: {
  sessionFile: string;
  sessionId: string;
  prompt: string;
  responseText: string;
  provider: string;
  model: string;
  usage?: {
    input?: number;
    output?: number;
    cacheRead?: number;
    cacheWrite?: number;
    total?: number;
  };
}): Promise<void> {
  await ensureSessionHeader({ sessionFile: params.sessionFile, sessionId: params.sessionId });

  const sessionManager = SessionManager.open(params.sessionFile);

  sessionManager.appendMessage({
    role: "user",
    content: params.prompt,
    timestamp: Date.now(),
  });

  const input = params.usage?.input ?? 0;
  const output = params.usage?.output ?? 0;
  sessionManager.appendMessage({
    role: "assistant",
    content: [{ type: "text", text: params.responseText }],
    api: "openai-responses",
    provider: params.provider,
    model: params.model,
    usage: {
      input,
      output,
      cacheRead: params.usage?.cacheRead ?? 0,
      cacheWrite: params.usage?.cacheWrite ?? 0,
      totalTokens: input + output,
      cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 },
    },
    stopReason: "stop",
    timestamp: Date.now(),
  });

  emitSessionTranscriptUpdate(params.sessionFile);
}
