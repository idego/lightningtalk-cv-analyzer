import { NextResponse } from "next/server";
import { analysisAccessTokenForUser } from "@/lib/analysis-access";
import { getWebUser } from "@/lib/web-user";

const INTERNAL_API_URL = process.env.INTERNAL_API_URL ?? "http://localhost:8000";

export async function POST(
  _request: Request,
  context: { params: Promise<{ analysisId: string }> },
) {
  const user = await getWebUser();
  const { analysisId } = await context.params;
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  const token = analysisAccessTokenForUser(user.id);
  const upstream = await fetch(
    `${INTERNAL_API_URL}/analyses/${encodeURIComponent(analysisId)}/share`,
    { method: "POST", headers: { "X-Analysis-Access-Token": token } },
  );
  return NextResponse.json(await upstream.json(), { status: upstream.status });
}
