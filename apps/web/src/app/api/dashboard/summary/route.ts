import { NextResponse } from "next/server";
import { proxyInternalJson } from "@/lib/internal-api";
import { getWebUser } from "@/lib/web-user";

export async function GET() {
  const user = await getWebUser();
  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  return proxyInternalJson("/internal/usage/summary", { cache: "no-store" });
}
