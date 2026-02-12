import type { MsgContext } from "../../auto-reply/templating.js";
import type { OpenClawConfig } from "../../config/types.openclaw.js";
import {
  buildAgentMainSessionKey,
  DEFAULT_AGENT_ID,
  normalizeMainKey,
} from "../../routing/session-key.js";
import { resolveAgentRoute } from "../../routing/resolve-route.js";
import { normalizeE164 } from "../../utils.js";
import { resolveGroupSessionKey } from "./group.js";
import type { SessionScope } from "./types.js";

// Decide which session bucket to use (per-sender vs global).
export function deriveSessionKey(scope: SessionScope, ctx: MsgContext) {
  if (scope === "global") return "global";
  const resolvedGroup = resolveGroupSessionKey(ctx);
  if (resolvedGroup) return resolvedGroup.key;
  const from = ctx.From ? normalizeE164(ctx.From) : "";
  return from || "unknown";
}

/**
 * Resolve the session key with a canonical direct-chat bucket (default: "main").
 * All non-group direct chats collapse to this bucket; groups stay isolated.
 */
export function resolveSessionKey(
  scope: SessionScope,
  ctx: MsgContext,
  mainKey?: string,
  cfg?: OpenClawConfig,
) {
  const explicit = ctx.SessionKey?.trim();
  if (explicit) return explicit.toLowerCase();
  const raw = deriveSessionKey(scope, ctx);
  if (scope === "global") return raw;
  const canonicalMainKey = normalizeMainKey(mainKey);
  const canonical = buildAgentMainSessionKey({
    agentId: DEFAULT_AGENT_ID,
    mainKey: canonicalMainKey,
  });
  const isGroup = raw.includes(":group:") || raw.includes(":channel:");
  if (!isGroup) return canonical;

  // For groups, resolve the correct agent from bindings if config is provided
  if (cfg) {
    const groupMatch = raw.match(/:(group|channel):([^:]+)$/);
    if (groupMatch) {
      const [, kind, peerId] = groupMatch;
      const route = resolveAgentRoute({
        cfg,
        channel: ctx.Provider ?? ctx.Surface ?? "unknown",
        accountId: ctx.AccountId,
        peer: { kind: kind as "group" | "channel", id: peerId },
      });
      return `agent:${route.agentId}:${raw}`;
    }
  }

  return `agent:${DEFAULT_AGENT_ID}:${raw}`;
}
