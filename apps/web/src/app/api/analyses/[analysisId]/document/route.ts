import { NextResponse } from "next/server";
import {
  analysisOwnerHeaders,
  INTERNAL_API_URL,
} from "@/lib/internal-api";
import { getWebUser } from "@/lib/web-user";

const FORWARDED_HEADERS = [
  "Content-Type",
  "Content-Disposition",
  "Content-Length",
  "Cache-Control",
];

export async function GET(
  _request: Request,
  context: { params: Promise<{ analysisId: string }> },
) {
  const user = await getWebUser();
  const { analysisId } = await context.params;
  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  let upstream: Response;
  try {
    upstream = await fetch(
      `${INTERNAL_API_URL}/analyses/${encodeURIComponent(analysisId)}/document`,
      { cache: "no-store", headers: analysisOwnerHeaders(user.id) },
    );
  } catch {
    return NextResponse.json({ error: "upstream_unavailable" }, { status: 502 });
  }

  if (!upstream.ok) {
    return NextResponse.json(
      { detail: upstream.status === 404 ? "analysis_not_found" : "upstream_error" },
      { status: upstream.status },
    );
  }

  const headers = new Headers();
  for (const name of FORWARDED_HEADERS) {
    const value = upstream.headers.get(name);
    if (value) headers.set(name, value);
  }
  if (!headers.has("Cache-Control")) {
    headers.set("Cache-Control", "private, no-store");
  }
  return new Response(upstream.body, { status: upstream.status, headers });
}
