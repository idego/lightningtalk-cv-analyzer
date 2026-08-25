import { NextResponse } from "next/server";
import { analysisAccessTokenForUser } from "@/lib/analysis-access";
import { getWebUser } from "@/lib/web-user";

const INTERNAL_API_URL = process.env.INTERNAL_API_URL ?? "http://localhost:8000";

export async function POST(
  _request: Request,
  context: { params: Promise<{ analysisId: string }> },
) {
  const user = await getWebUser();
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  const { analysisId } = await context.params;
  const token = analysisAccessTokenForUser(user.id);
  const upstream = await fetch(
    `${INTERNAL_API_URL}/analyses/${encodeURIComponent(analysisId)}/ai/retry`,
    {
      method: "POST",
      cache: "no-store",
      headers: { "X-Analysis-Access-Token": token },
    },
  );
  const data = await upstream.json();
  if (upstream.ok) data.analysis_access_token = token;
  return NextResponse.json(data, { status: upstream.status });
}
