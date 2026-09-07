import { NextResponse } from "next/server";
import { analysisOwnerHeaders, proxyInternalJson } from "@/lib/internal-api";
import { getWebUser } from "@/lib/web-user";

type Context = { params: Promise<{ analysisId: string }> };

async function values(context: Context) {
  const user = await getWebUser();
  const { analysisId } = await context.params;
  return { user, analysisId };
}

export async function GET(_request: Request, context: Context) {
  const { user, analysisId } = await values(context);
  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  return proxyInternalJson(`/analyses/${encodeURIComponent(analysisId)}`, {
    cache: "no-store",
    headers: analysisOwnerHeaders(user.id),
  });
}

export async function DELETE(_request: Request, context: Context) {
  const { user, analysisId } = await values(context);
  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  return proxyInternalJson(`/analyses/${encodeURIComponent(analysisId)}`, {
    method: "DELETE",
    headers: analysisOwnerHeaders(user.id),
  });
}
