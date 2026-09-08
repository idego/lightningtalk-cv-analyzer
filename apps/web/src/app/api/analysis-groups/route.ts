import { NextResponse } from "next/server";
import { analysisOwnerHeaders, proxyInternalJson } from "@/lib/internal-api";
import { getWebUser } from "@/lib/web-user";

async function ownerId() {
  return (await getWebUser())?.id ?? null;
}

export async function GET() {
  const userId = await ownerId();
  if (!userId) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  return proxyInternalJson("/analysis-groups", {
    cache: "no-store",
    headers: analysisOwnerHeaders(userId),
  });
}

export async function POST(req: Request) {
  const userId = await ownerId();
  if (!userId) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  const body = await req.json().catch(() => null) as { name?: unknown } | null;
  if (!body || typeof body.name !== "string") {
    return NextResponse.json({ error: "invalid_group_name" }, { status: 400 });
  }
  return proxyInternalJson("/analysis-groups", {
    method: "POST",
    body: JSON.stringify({ name: body.name }),
    headers: { ...analysisOwnerHeaders(userId), "Content-Type": "application/json" },
  });
}
