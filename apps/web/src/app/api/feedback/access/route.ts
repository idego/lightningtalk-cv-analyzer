import { NextResponse } from "next/server";
import {
  feedbackCollectionEnabled,
  feedbackRole,
  grantFeedbackAccess,
  listFeedbackMembers,
  revokeFeedbackAccess,
  setFeedbackCollectionEnabled,
} from "@/lib/feedback-access";
import { getWebUser } from "@/lib/web-user";

async function owner() {
  const user = await getWebUser();
  return user && feedbackRole(user.email) === "owner" ? user : null;
}

async function jsonBody(request: Request): Promise<Record<string, unknown> | null> {
  const body = await request.json().catch(() => null);
  return body && typeof body === "object" && !Array.isArray(body)
    ? body as Record<string, unknown>
    : null;
}

export async function GET() {
  const user = await owner();
  if (!user) {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }
  return NextResponse.json({
    members: listFeedbackMembers(),
    collectionEnabled: feedbackCollectionEnabled(),
  });
}

export async function PUT(request: Request) {
  const user = await owner();
  if (!user) {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }
  const body = await jsonBody(request);
  if (
    !body
    || typeof body.email !== "string"
    || !(body.role === "owner" || body.role === "reviewer")
  ) {
    return NextResponse.json({ error: "Invalid request" }, { status: 422 });
  }
  try {
    return NextResponse.json({
      email: grantFeedbackAccess(body.email, body.role, user.email),
    });
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Invalid request" },
      { status: 422 },
    );
  }
}

export async function PATCH(request: Request) {
  const user = await owner();
  if (!user) {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }
  const body = await jsonBody(request);
  if (!body || typeof body.collectionEnabled !== "boolean") {
    return NextResponse.json({ error: "Invalid request" }, { status: 422 });
  }
  return NextResponse.json({
    collectionEnabled: setFeedbackCollectionEnabled(
      body.collectionEnabled,
      user.email,
    ),
  });
}

export async function DELETE(request: Request) {
  const user = await owner();
  if (!user) {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }
  const body = await jsonBody(request);
  if (!body || typeof body.email !== "string") {
    return NextResponse.json({ error: "Invalid request" }, { status: 422 });
  }
  try {
    return NextResponse.json({ revoked: revokeFeedbackAccess(body.email) });
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Invalid request" },
      { status: 409 },
    );
  }
}
