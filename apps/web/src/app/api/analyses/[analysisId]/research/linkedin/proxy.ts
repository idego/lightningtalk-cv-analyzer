import { NextResponse } from "next/server";
import { getWebUser } from "@/lib/web-user";

const INTERNAL_API_URL = process.env.INTERNAL_API_URL ?? "http://localhost:8000";

export async function proxyLinkedInResearch(req: Request, context: { params: Promise<{ analysisId: string }> }) {
  if (!(await getWebUser())) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  const { analysisId } = await context.params;
  const body = await req.json().catch(() => ({}));
  if (typeof body.accessToken !== "string") return NextResponse.json({ error: "Not found" }, { status: 404 });
  const upstream = await fetch(`${INTERNAL_API_URL}/analyses/${encodeURIComponent(analysisId)}/research/linkedin/discovery`, { method: "POST", headers: { "X-Analysis-Access-Token": body.accessToken } });
  const data = await upstream.json().catch(() => ({}));
  return NextResponse.json(data, { status: upstream.status });
}
