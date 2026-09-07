import { NextResponse } from "next/server";
import { getWebUser } from "@/lib/web-user";

const INTERNAL_API_URL = process.env.INTERNAL_API_URL ?? "http://localhost:8000";
const FORWARDED_HEADERS = ["Content-Type", "Content-Disposition", "Content-Length", "Cache-Control"];

export async function GET(
  request: Request,
  context: { params: Promise<{ analysisId: string }> },
) {
  const user = await getWebUser();
  const { analysisId } = await context.params;
  const shareToken = request.headers.get("X-Analysis-Share-Token");
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  if (!shareToken) return NextResponse.json({ detail: "analysis_not_found" }, { status: 404 });
  let upstream: Response;
  try {
    upstream = await fetch(
      `${INTERNAL_API_URL}/shared/analyses/${encodeURIComponent(analysisId)}/document`,
      { cache: "no-store", headers: { "X-Analysis-Share-Token": shareToken } },
    );
  } catch {
    return NextResponse.json({ error: "upstream_unavailable" }, { status: 502 });
  }
  if (!upstream.ok) {
    return NextResponse.json(
      { detail: "analysis_not_found" },
      { status: upstream.status },
    );
  }
  const headers = new Headers();
  for (const name of FORWARDED_HEADERS) {
    const value = upstream.headers.get(name);
    if (value) headers.set(name, value);
  }
  if (!headers.has("Cache-Control")) headers.set("Cache-Control", "private, no-store");
  return new Response(upstream.body, { status: 200, headers });
}
