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
  return proxyInternalJson("/analyses", {
    cache: "no-store",
    headers: analysisOwnerHeaders(userId),
  });
}

export async function DELETE() {
  const userId = await ownerId();
  if (!userId) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  return proxyInternalJson("/analyses", {
    method: "DELETE",
    headers: analysisOwnerHeaders(userId),
  });
}
