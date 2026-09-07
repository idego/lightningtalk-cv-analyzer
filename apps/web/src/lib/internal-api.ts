import { RESEARCH_ERROR_REASONS } from "./research-error-details";
import { NextResponse } from "next/server";

export const INTERNAL_API_URL =
  process.env.INTERNAL_API_URL ?? "http://localhost:8000";

export function analysisOwnerHeaders(userId: string): Record<string, string> {
  return { "X-Analysis-Owner-Id": userId };
}

export type InternalJsonResult = {
  status: number;
  ok: boolean;
  payload: unknown;
};

export async function fetchInternalJson(
  path: string,
  init: RequestInit = {},
): Promise<InternalJsonResult> {
  let upstream: Response;
  try {
    upstream = await fetch(`${INTERNAL_API_URL}${path}`, init);
  } catch {
    return {
      status: 502,
      ok: false,
      payload: { error: "upstream_unavailable" },
    };
  }

  const text = await upstream.text().catch(() => "");
  if (!text) {
    return { status: upstream.status, ok: upstream.ok, payload: {} };
  }
  try {
    const payload = JSON.parse(text);
    const reason = upstream.headers.get("X-Research-Error-Reason");
    if (!upstream.ok && payload && typeof payload === "object" && !Array.isArray(payload)
      && reason && RESEARCH_ERROR_REASONS.has(reason)) payload.error_reason = reason;
    return { status: upstream.status, ok: upstream.ok, payload };
  } catch {
    return {
      status: upstream.ok ? 502 : upstream.status,
      ok: false,
      payload: { error: "upstream_invalid_response" },
    };
  }
}

export async function proxyInternalJson(
  path: string,
  init: RequestInit = {},
): Promise<NextResponse> {
  const result = await fetchInternalJson(path, init);
  return NextResponse.json(result.payload, { status: result.status });
}
