import { NextResponse } from "next/server";
import { getWebUser } from "@/lib/web-user";

const INTERNAL_API_URL = process.env.INTERNAL_API_URL ?? "http://localhost:8000";

export async function POST(
  _req: Request,
  context: { params: Promise<{ analysisId: string }> },
) {
  if (!(await getWebUser())) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  const { analysisId } = await context.params;
  const upstream = await fetch(
    `${INTERNAL_API_URL}/analyses/${encodeURIComponent(analysisId)}/research/company`,
    { method: "POST" },
  );
  const data = await upstream.json().catch(() => ({}));
  return NextResponse.json(data, { status: upstream.status });
}
