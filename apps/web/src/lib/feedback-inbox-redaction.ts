import type { FeedbackRole } from "./feedback-access";

/**
 * Reviewers see pseudonymous actors only. The author's email is owner-only data,
 * so it is removed from inbox items before they leave the web proxy.
 */
export function redactInboxForRole(payload: unknown, role: FeedbackRole): unknown {
  if (role === "owner" || !payload || typeof payload !== "object" || Array.isArray(payload)) {
    return payload;
  }
  const items = (payload as { items?: unknown }).items;
  if (!Array.isArray(items)) return payload;
  return {
    ...payload,
    items: items.map((item) => {
      if (!item || typeof item !== "object" || Array.isArray(item)) return item;
      const { actor_email: _actorEmail, ...rest } = item as Record<string, unknown>;
      void _actorEmail;
      return rest;
    }),
  };
}
