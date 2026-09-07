import { NextResponse } from "next/server";
import { feedbackCollectionEnabled } from "@/lib/feedback-access";
import { analysisOwnerHeaders, proxyInternalJson } from "@/lib/internal-api";
import { getWebUser } from "@/lib/web-user";

type Context = {
  params: Promise<{ analysisId: string; targetId: string }>;
};

async function values(context: Context) {
  const user = await getWebUser();
  const params = await context.params;
  return { user, params };
}

export async function PUT(request: Request, context: Context) {
  const { user, params } = await values(context);
  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  if (!feedbackCollectionEnabled()) {
    return NextResponse.json({ error: "feedback_disabled" }, { status: 404 });
  }
  const body = await request.text();
  if (body.length > 524_288) {
    return NextResponse.json({ error: "Request too large" }, { status: 413 });
  }
  return proxyInternalJson(
    `/analyses/${encodeURIComponent(params.analysisId)}/feedback/${encodeURIComponent(params.targetId)}`,
    {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        ...analysisOwnerHeaders(user.id),
        "X-Feedback-Actor-Email": user.email,
      },
      body,
    },
  );
}

export async function DELETE(_request: Request, context: Context) {
  const { user, params } = await values(context);
  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  if (!feedbackCollectionEnabled()) {
    return NextResponse.json({ error: "feedback_disabled" }, { status: 404 });
  }
  return proxyInternalJson(
    `/analyses/${encodeURIComponent(params.analysisId)}/feedback/${encodeURIComponent(params.targetId)}`,
    { method: "DELETE", headers: analysisOwnerHeaders(user.id) },
  );
}
