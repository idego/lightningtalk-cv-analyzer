import { NextResponse } from "next/server";
import { feedbackRole } from "@/lib/feedback-access";
import { proxyInternalJson } from "@/lib/internal-api";
import { getWebUser } from "@/lib/web-user";

type Context = { params: Promise<{ targetId: string; actorHash: string }> };

async function reviewer(context: Context) {
  const user = await getWebUser();
  const params = await context.params;
  return { user, params, role: user ? feedbackRole(user.email) : null };
}

export async function PUT(request: Request, context: Context) {
  const { user, params, role } = await reviewer(context);
  if (!user || !role) {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }
  const body = await request.text();
  if (body.length > 2_048) {
    return NextResponse.json({ error: "Request too large" }, { status: 413 });
  }
  return proxyInternalJson(
    `/internal/feedback/${encodeURIComponent(params.targetId)}/${encodeURIComponent(params.actorHash)}/triage`,
    {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        "X-Feedback-Maintainer": user.id,
      },
      body,
    },
  );
}

export async function DELETE(_request: Request, context: Context) {
  const { user, params, role } = await reviewer(context);
  if (!user || !role) {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }
  return proxyInternalJson(
    `/internal/feedback/${encodeURIComponent(params.targetId)}/${encodeURIComponent(params.actorHash)}`,
    {
      method: "DELETE",
      headers: { "X-Feedback-Maintainer": user.id },
    },
  );
}
