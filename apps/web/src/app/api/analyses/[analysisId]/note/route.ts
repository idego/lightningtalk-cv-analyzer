import { NextResponse } from "next/server";
import { analysisOwnerHeaders, proxyInternalJson } from "@/lib/internal-api";
import { getWebUser } from "@/lib/web-user";

type Context = { params: Promise<{ analysisId: string }> };

async function values(context: Context) {
  const user = await getWebUser();
  const { analysisId } = await context.params;
  return { user, path: `/analyses/${encodeURIComponent(analysisId)}/note` };
}

export async function GET(_request: Request, context: Context) {
  const { user, path } = await values(context);
  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  return proxyInternalJson(path, { cache: "no-store", headers: analysisOwnerHeaders(user.id) });
}

export async function PUT(request: Request, context: Context) {
  const { user, path } = await values(context);
  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  const body = await request.json().catch(() => null) as { content?: unknown } | null;
  if (!body || typeof body.content !== "string") {
    return NextResponse.json({ error: "invalid_note" }, { status: 400 });
  }
  return proxyInternalJson(path, {
    method: "PUT",
    body: JSON.stringify({ content: body.content }),
    headers: { ...analysisOwnerHeaders(user.id), "Content-Type": "application/json" },
  });
}

export async function DELETE(_request: Request, context: Context) {
  const { user, path } = await values(context);
  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  return proxyInternalJson(path, { method: "DELETE", headers: analysisOwnerHeaders(user.id) });
}
