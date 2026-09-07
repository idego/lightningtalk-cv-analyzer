import { NextResponse } from "next/server";
import { analysisOwnerHeaders, proxyInternalJson } from "@/lib/internal-api";
import { getWebUser } from "@/lib/web-user";

export async function POST(req: Request) {
  const user = await getWebUser();
  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const requestId = req.headers.get("X-Analysis-Request-Id");
  if (!requestId) {
    return NextResponse.json({ error: "Missing request id" }, { status: 400 });
  }

  return proxyInternalJson("/analyze/cancel", {
    method: "POST",
    headers: {
      ...analysisOwnerHeaders(user.id),
      "X-Analysis-Request-Id": requestId,
    },
  });
}
