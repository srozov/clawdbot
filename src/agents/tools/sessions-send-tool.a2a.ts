import crypto from "node:crypto";

import { appendAssistantMessageToSessionTranscript } from "../../config/sessions/transcript.js";
import { resolveAgentIdFromSessionKey } from "../../config/sessions.js";
import { callGateway } from "../../gateway/call.js";
import { formatErrorMessage } from "../../infra/errors.js";
import { createSubsystemLogger } from "../../logging/subsystem.js";
import type { GatewayMessageChannel } from "../../utils/message-channel.js";
import { AGENT_LANE_NESTED } from "../lanes.js";
import { readLatestAssistantReply, runAgentStep } from "./agent-step.js";
import { resolveAnnounceTarget } from "./sessions-announce-target.js";
import {
  buildAgentToAgentAnnounceContext,
  buildAgentToAgentReplyContext,
  isReplySkip,
} from "./sessions-send-helpers.js";

const log = createSubsystemLogger("agents/sessions-send");

export async function runSessionsSendA2AFlow(params: {
  targetSessionKey: string;
  displayKey: string;
  message: string;
  announceTimeoutMs: number;
  maxPingPongTurns: number;
  requesterSessionKey?: string;
  requesterChannel?: GatewayMessageChannel;
  roundOneReply?: string;
  waitRunId?: string;
}) {
  const runContextId = params.waitRunId ?? "unknown";
  try {
    let primaryReply = params.roundOneReply;
    let latestReply = params.roundOneReply;
    if (!primaryReply && params.waitRunId) {
      const waitMs = Math.min(params.announceTimeoutMs, 60_000);
      const wait = (await callGateway({
        method: "agent.wait",
        params: {
          runId: params.waitRunId,
          timeoutMs: waitMs,
        },
        timeoutMs: waitMs + 2000,
      })) as { status?: string };
      if (wait?.status === "ok") {
        primaryReply = await readLatestAssistantReply({
          sessionKey: params.targetSessionKey,
        });
        latestReply = primaryReply;
      }
    }
    if (!latestReply) return;

    const announceTarget = await resolveAnnounceTarget({
      sessionKey: params.targetSessionKey,
      displayKey: params.displayKey,
    });
    const targetChannel = announceTarget?.channel ?? "unknown";

    // Ping-pong loop: stay in target session, poll for replies, forward to requester
    if (params.maxPingPongTurns > 0 && params.requesterSessionKey && announceTarget) {
      let incomingMessage = latestReply;
      for (let turn = 1; turn <= params.maxPingPongTurns; turn += 1) {
        // Check for new reply in target session by running another agent step
        const replyPrompt = buildAgentToAgentReplyContext({
          requesterSessionKey: params.requesterSessionKey,
          requesterChannel: params.requesterChannel,
          targetSessionKey: params.displayKey,
          targetChannel,
          currentRole: "target",
          turn,
          maxTurns: params.maxPingPongTurns,
        });
        const replyText = await runAgentStep({
          sessionKey: params.targetSessionKey,
          message: incomingMessage ?? "Continue the conversation.",
          extraSystemPrompt: replyPrompt,
          timeoutMs: params.announceTimeoutMs,
          lane: AGENT_LANE_NESTED,
        });
        if (!replyText || isReplySkip(replyText)) {
          break;
        }
        // Forward this reply to the requester's channel
        latestReply = replyText;
        try {
          await callGateway({
            method: "send",
            params: {
              to: announceTarget.to,
              message: replyText.trim(),
              channel: announceTarget.channel,
              accountId: announceTarget.accountId,
              threadId: announceTarget.threadId,
              idempotencyKey: crypto.randomUUID(),
            },
            timeoutMs: 10_000,
          });
        } catch (err) {
          log.warn("sessions_send pong delivery failed", {
            runId: runContextId,
            channel: announceTarget.channel,
            to: announceTarget.to,
            error: formatErrorMessage(err),
          });
        }
        incomingMessage = replyText;
      }
    }

    // Write A2A announce context to requester's session (conductor understands A2A, subagent doesn't)
    const announceContext = buildAgentToAgentAnnounceContext({
      requesterSessionKey: params.requesterSessionKey,
      requesterChannel: params.requesterChannel,
      targetSessionKey: params.displayKey,
      targetChannel,
      originalMessage: params.message,
      roundOneReply: primaryReply,
      latestReply,
    });
    if (params.requesterSessionKey) {
      const requesterAgentId = resolveAgentIdFromSessionKey(params.requesterSessionKey);
      await appendAssistantMessageToSessionTranscript({
        agentId: requesterAgentId,
        sessionKey: params.requesterSessionKey,
        text: announceContext,
      }).catch((err) => {
        log.warn("failed to write A2A announce context to requester session", {
          runId: runContextId,
          sessionKey: params.requesterSessionKey,
          error: formatErrorMessage(err),
        });
      });
    }

    // Deliver the reply directly (no Claude CLI involvement for announce)
    if (announceTarget && latestReply && latestReply.trim()) {
      try {
        await callGateway({
          method: "send",
          params: {
            to: announceTarget.to,
            message: latestReply.trim(),
            channel: announceTarget.channel,
            accountId: announceTarget.accountId,
            threadId: announceTarget.threadId,
            idempotencyKey: crypto.randomUUID(),
          },
          timeoutMs: 10_000,
        });
      } catch (err) {
        log.warn("sessions_send announce delivery failed", {
          runId: runContextId,
          channel: announceTarget.channel,
          to: announceTarget.to,
          error: formatErrorMessage(err),
        });
      }
    }

    // Fallback for non-blocking sends to subagent sessions: no external channel can be
    // resolved from a subagent key, so trigger the requester agent directly — mirroring
    // how sessions_spawn announces work. Blocking sends don't need this because the reply
    // is already returned in the sessions_send tool result.
    if (!announceTarget && params.waitRunId && params.requesterSessionKey && latestReply?.trim()) {
      const requesterTarget = await resolveAnnounceTarget({
        sessionKey: params.requesterSessionKey,
        displayKey: params.requesterSessionKey,
      });
      if (requesterTarget) {
        try {
          await callGateway({
            method: "agent",
            params: {
              sessionKey: params.requesterSessionKey,
              message: latestReply.trim(),
              deliver: true,
              channel: requesterTarget.channel,
              accountId: requesterTarget.accountId,
              to: requesterTarget.to,
              threadId:
                requesterTarget.threadId != null && requesterTarget.threadId !== ""
                  ? requesterTarget.threadId
                  : undefined,
              idempotencyKey: crypto.randomUUID(),
            },
            expectFinal: true,
            timeoutMs: params.announceTimeoutMs,
          });
        } catch (err) {
          log.warn("sessions_send requester fallback delivery failed", {
            runId: runContextId,
            sessionKey: params.requesterSessionKey,
            error: formatErrorMessage(err),
          });
        }
      }
    }
  } catch (err) {
    log.warn("sessions_send announce flow failed", {
      runId: runContextId,
      error: formatErrorMessage(err),
    });
  }
}
