import { NextResponse } from "next/server";
import { getWebUser } from "@/lib/web-user";

const INTERNAL_API_URL = process.env.INTERNAL_API_URL ?? "http://localhost:8000";

export async function GET(
  request: Request,
  context: { params: Promise<{ analysisId: string }> },
) {
  const user = await getWebUser();
  const { analysisId } = await context.params;
  const shareToken = request.headers.get("X-Analysis-Share-Token");
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  if (!shareToken) return NextResponse.json({ detail: "analysis_not_found" }, { status: 404 });
  const upstream = await fetch(
    `${INTERNAL_API_URL}/shared/analyses/${encodeURIComponent(analysisId)}`,
    { cache: "no-store", headers: { "X-Analysis-Share-Token": shareToken } },
  );
  return NextResponse.json(await upstream.json(), { status: upstream.status });
}
