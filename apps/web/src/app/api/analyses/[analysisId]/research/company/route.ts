import { NextResponse } from "next/server";
import { analysisOwnerHeaders, proxyInternalJson } from "@/lib/internal-api";
import { getWebUser } from "@/lib/web-user";

export async function POST(
  request: Request,
  context: { params: Promise<{ analysisId: string }> },
) {
  const user = await getWebUser();
  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  const { analysisId } = await context.params;
  const body = await request.json().catch(() => ({})) as { refresh?: unknown };
  return proxyInternalJson(
    `/analyses/${encodeURIComponent(analysisId)}/research/company`,
    {
      method: "POST",
      headers: {
        ...analysisOwnerHeaders(user.id),
        "X-AI-Enabled": "true",
        "X-Research-Refresh": body.refresh === true ? "true" : "false",
      },
    },
  );
}
