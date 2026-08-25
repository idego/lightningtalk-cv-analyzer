import { NextResponse } from "next/server";
import { analysisAccessTokenForUser } from "@/lib/analysis-access";
import { getWebUser } from "@/lib/web-user";

const INTERNAL_API_URL = process.env.INTERNAL_API_URL ?? "http://localhost:8000";

async function accessToken() {
  const user = await getWebUser();
  return user ? analysisAccessTokenForUser(user.id) : null;
}

export async function GET() {
  const token = await accessToken();
  if (!token) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  const upstream = await fetch(`${INTERNAL_API_URL}/analyses`, {
    cache: "no-store",
    headers: { "X-Analysis-Access-Token": token },
  });
  return NextResponse.json(await upstream.json(), { status: upstream.status });
}

export async function DELETE() {
  const token = await accessToken();
  if (!token) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  const upstream = await fetch(`${INTERNAL_API_URL}/analyses`, {
    method: "DELETE",
    headers: { "X-Analysis-Access-Token": token },
  });
  return NextResponse.json(await upstream.json(), { status: upstream.status });
}
