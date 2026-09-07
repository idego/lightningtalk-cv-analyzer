import { NextResponse } from "next/server";
import { feedbackRole } from "@/lib/feedback-access";
import { fetchInternalJson, proxyInternalJson } from "@/lib/internal-api";
import { getWebUser } from "@/lib/web-user";

export async function GET() {
  const user = await getWebUser();
  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  const result = await fetchInternalJson("/settings/retention", {
    cache: "no-store",
  });
  if (!result.ok || typeof result.payload !== "object" || result.payload === null) {
    return NextResponse.json(result.payload, { status: result.status });
  }
  return NextResponse.json(
    {
      ...(result.payload as Record<string, unknown>),
      canManage: feedbackRole(user.email) === "owner",
    },
    { status: result.status },
  );
}

export async function PUT(request: Request) {
  const user = await getWebUser();
  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  if (feedbackRole(user.email) !== "owner") {
    return NextResponse.json({ error: "retention_owner_required" }, { status: 403 });
  }
  const body = await request.json().catch(() => ({}));
  const internalAdminSecret = process.env.BETTER_AUTH_SECRET;
  if (!internalAdminSecret) {
    return NextResponse.json(
      { error: "retention_admin_unconfigured" },
      { status: 503 },
    );
  }
  return proxyInternalJson("/settings/retention", {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
      "X-Internal-Admin-Secret": internalAdminSecret,
    },
    body: JSON.stringify(body),
  });
}
