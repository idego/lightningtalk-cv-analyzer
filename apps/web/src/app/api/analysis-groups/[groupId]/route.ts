import { NextResponse } from "next/server";
import { analysisOwnerHeaders, proxyInternalJson } from "@/lib/internal-api";
import { getWebUser } from "@/lib/web-user";

type Context = { params: Promise<{ groupId: string }> };

export async function DELETE(_request: Request, context: Context) {
  const user = await getWebUser();
  const { groupId } = await context.params;
  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  return proxyInternalJson(`/analysis-groups/${encodeURIComponent(groupId)}`, {
    method: "DELETE",
    headers: analysisOwnerHeaders(user.id),
  });
}
