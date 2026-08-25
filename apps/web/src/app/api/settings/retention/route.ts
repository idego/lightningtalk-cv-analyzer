import { NextResponse } from "next/server";
import { getWebUser } from "@/lib/web-user";

const INTERNAL_API_URL = process.env.INTERNAL_API_URL ?? "http://localhost:8000";

export async function GET() {
  if (!(await getWebUser())) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  const upstream = await fetch(`${INTERNAL_API_URL}/settings/retention`, {
    cache: "no-store",
  });
  return NextResponse.json(await upstream.json(), { status: upstream.status });
}

export async function PUT(request: Request) {
  if (!(await getWebUser())) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  const body = await request.json().catch(() => ({}));
  const upstream = await fetch(`${INTERNAL_API_URL}/settings/retention`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return NextResponse.json(await upstream.json(), { status: upstream.status });
}
