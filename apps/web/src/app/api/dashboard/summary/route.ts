import { NextResponse } from "next/server";
import {
  internalApiSecret,
  internalSecretHeaders,
  internalSecretUnconfigured,
  proxyInternalJson,
} from "@/lib/internal-api";
import { getWebUser } from "@/lib/web-user";

export async function GET() {
  const user = await getWebUser();
  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  const secret = internalApiSecret();
  if (!secret) return internalSecretUnconfigured();
  return proxyInternalJson("/internal/usage/summary", {
    cache: "no-store",
    headers: internalSecretHeaders(secret),
  });
}
