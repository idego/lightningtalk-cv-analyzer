import { createHmac } from "node:crypto";

/** Preserve the original Profile Builder owner key without sending it to the browser. */
export function profileBuilderOwnerToken(userId: string): string {
  const secret = process.env.BETTER_AUTH_SECRET;
  if (!secret && process.env.NODE_ENV === "production") {
    throw new Error("BETTER_AUTH_SECRET is required");
  }
  return createHmac("sha256", secret ?? "local-dev-secret-change-this-0123456789")
    .update(`cv-analysis-history:${userId}`)
    .digest("hex");
}
