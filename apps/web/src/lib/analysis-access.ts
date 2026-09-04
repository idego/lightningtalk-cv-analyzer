import { createHmac } from "node:crypto";

const secret =
  process.env.BETTER_AUTH_SECRET ??
  "local-dev-secret-change-this-0123456789";

export function analysisAccessTokenForUser(userId: string): string {
  return createHmac("sha256", secret)
    .update(`cv-analysis-history:${userId}`)
    .digest("hex");
}
