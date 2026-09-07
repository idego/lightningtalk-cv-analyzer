import { NextResponse } from "next/server";
import { feedbackRole } from "@/lib/feedback-access";
import { proxyInternalJson } from "@/lib/internal-api";
import { getWebUser } from "@/lib/web-user";

export async function GET(request: Request) {
  const user = await getWebUser();
  if (!user || !feedbackRole(user.email)) {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }
  const query = new URL(request.url).search;
  return proxyInternalJson(`/internal/feedback${query}`, { cache: "no-store" });
}
