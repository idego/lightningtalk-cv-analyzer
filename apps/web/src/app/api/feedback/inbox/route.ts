import { NextResponse } from "next/server";
import { feedbackRole } from "@/lib/feedback-access";
import { redactInboxForRole } from "@/lib/feedback-inbox-redaction";
import {
  fetchInternalJson,
  internalApiSecret,
  internalSecretHeaders,
  internalSecretUnconfigured,
} from "@/lib/internal-api";
import { getWebUser } from "@/lib/web-user";

export async function GET(request: Request) {
  const user = await getWebUser();
  const role = user ? feedbackRole(user.email) : null;
  if (!user || !role) {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }
  const secret = internalApiSecret();
  if (!secret) return internalSecretUnconfigured();
  const query = new URL(request.url).search;
  const result = await fetchInternalJson(`/internal/feedback${query}`, {
    cache: "no-store",
    headers: internalSecretHeaders(secret),
  });
  const payload = result.ok ? redactInboxForRole(result.payload, role) : result.payload;
  return NextResponse.json(payload, { status: result.status });
}
