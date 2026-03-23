import { loadConfig } from "../config/config.js";
import { loadSessionStore, resolveStorePath } from "../config/sessions.js";
import { getAgentRunContext, registerAgentRunContext } from "../infra/agent-events.js";
import { toAgentRequestSessionKey } from "../routing/session-key.js";

export function resolveSessionKeyForRun(runId: string, agentIdHint?: string) {
  const cached = getAgentRunContext(runId)?.sessionKey;
  if (cached) return cached;

  // If agentId hint is provided, search only that agent's store
  if (agentIdHint) {
    const cfg = loadConfig();
    const storePath = resolveStorePath(cfg.session?.store, { agentId: agentIdHint });
    const store = loadSessionStore(storePath);
    const found = Object.entries(store).find(([, entry]) => entry?.sessionId === runId);
    const storeKey = found?.[0];
    if (storeKey) {
      const sessionKey = toAgentRequestSessionKey(storeKey) ?? storeKey;
      registerAgentRunContext(runId, { sessionKey });
      return sessionKey;
    }
  }

  // No cached context and no valid hint = can't determine sessionKey
  return undefined;
}
