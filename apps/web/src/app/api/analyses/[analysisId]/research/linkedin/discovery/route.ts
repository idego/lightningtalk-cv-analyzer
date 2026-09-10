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
  return proxyInternalJson(
    `/analyses/${encodeURIComponent(analysisId)}/research/linkedin/discovery`,
    {
      method: "POST",
      headers: {
        ...analysisOwnerHeaders(user.id),
        "X-AI-Enabled": "true",
        // The browser can never force a shared-cache refresh; the proxy pins it off.
        "X-Research-Refresh": "false",
      },
    },
  );
}
