import { NextResponse } from "next/server";
import { analysisOwnerHeaders, proxyInternalJson } from "@/lib/internal-api";
import { getWebUser } from "@/lib/web-user";

export async function GET(
  _request: Request,
  context: { params: Promise<{ analysisId: string }> },
) {
  const user = await getWebUser();
  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  const { analysisId } = await context.params;
  return proxyInternalJson(`/analyses/${encodeURIComponent(analysisId)}/usage`, {
    cache: "no-store",
    headers: analysisOwnerHeaders(user.id),
  });
}
