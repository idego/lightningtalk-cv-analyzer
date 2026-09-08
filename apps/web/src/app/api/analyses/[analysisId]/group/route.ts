import { NextResponse } from "next/server";
import { analysisOwnerHeaders, proxyInternalJson } from "@/lib/internal-api";
import { getWebUser } from "@/lib/web-user";

type Context = { params: Promise<{ analysisId: string }> };

export async function PUT(request: Request, context: Context) {
  const user = await getWebUser();
  const { analysisId } = await context.params;
  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  const body = await request.json().catch(() => null) as { group_id?: unknown } | null;
  if (!body || (body.group_id !== null && typeof body.group_id !== "string")) {
    return NextResponse.json({ error: "invalid_group_id" }, { status: 400 });
  }
  return proxyInternalJson(`/analyses/${encodeURIComponent(analysisId)}/group`, {
    method: "PUT",
    body: JSON.stringify({ group_id: body.group_id }),
    headers: { ...analysisOwnerHeaders(user.id), "Content-Type": "application/json" },
  });
}
