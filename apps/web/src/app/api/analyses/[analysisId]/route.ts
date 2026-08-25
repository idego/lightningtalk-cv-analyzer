import { NextResponse } from "next/server";
import { analysisAccessTokenForUser } from "@/lib/analysis-access";
import { getWebUser } from "@/lib/web-user";

const INTERNAL_API_URL = process.env.INTERNAL_API_URL ?? "http://localhost:8000";

async function contextValues(context: { params: Promise<{ analysisId: string }> }) {
  const user = await getWebUser();
  const { analysisId } = await context.params;
  return {
    analysisId,
    token: user ? analysisAccessTokenForUser(user.id) : null,
  };
}

export async function GET(
  _request: Request,
  context: { params: Promise<{ analysisId: string }> },
) {
  const { analysisId, token } = await contextValues(context);
  if (!token) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  const upstream = await fetch(
    `${INTERNAL_API_URL}/analyses/${encodeURIComponent(analysisId)}`,
    { cache: "no-store", headers: { "X-Analysis-Access-Token": token } },
  );
  const data = await upstream.json();
  if (upstream.ok) data.analysis_access_token = token;
  return NextResponse.json(data, { status: upstream.status });
}

export async function DELETE(
  _request: Request,
  context: { params: Promise<{ analysisId: string }> },
) {
  const { analysisId, token } = await contextValues(context);
  if (!token) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  const upstream = await fetch(
    `${INTERNAL_API_URL}/analyses/${encodeURIComponent(analysisId)}`,
    { method: "DELETE", headers: { "X-Analysis-Access-Token": token } },
  );
  return NextResponse.json(await upstream.json(), { status: upstream.status });
}
