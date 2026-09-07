import { NextResponse } from "next/server";
import { proxyInternalJson } from "@/lib/internal-api";
import { getWebUser } from "@/lib/web-user";

export async function GET(
  request: Request,
  context: { params: Promise<{ analysisId: string }> },
) {
  const user = await getWebUser();
  const { analysisId } = await context.params;
  const shareToken = request.headers.get("X-Analysis-Share-Token");
  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  if (!shareToken) {
    return NextResponse.json({ detail: "analysis_not_found" }, { status: 404 });
  }
  return proxyInternalJson(
    `/shared/analyses/${encodeURIComponent(analysisId)}`,
    {
      cache: "no-store",
      headers: { "X-Analysis-Share-Token": shareToken },
    },
  );
}
