import { NextResponse } from "next/server";
import { analysisAccessTokenForUser } from "@/lib/analysis-access";
import { getWebUser } from "@/lib/web-user";

const INTERNAL_API_URL = process.env.INTERNAL_API_URL ?? "http://localhost:8000";
const FORWARDED_HEADERS = ["Content-Type", "Content-Disposition", "Content-Length", "Cache-Control"];

export async function GET(
  _request: Request,
  context: { params: Promise<{ analysisId: string }> },
) {
  const user = await getWebUser();
  const { analysisId } = await context.params;
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  const token = analysisAccessTokenForUser(user.id);
  const upstream = await fetch(
    `${INTERNAL_API_URL}/analyses/${encodeURIComponent(analysisId)}/document`,
    { cache: "no-store", headers: { "X-Analysis-Access-Token": token } },
  );
  if (!upstream.ok) {
    return NextResponse.json(
      { detail: "analysis_not_found" },
      { status: upstream.status === 404 ? 404 : upstream.status },
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
