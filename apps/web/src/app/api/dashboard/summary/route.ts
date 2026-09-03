import { NextResponse } from "next/server";
import { getWebUser } from "@/lib/web-user";

const INTERNAL_API_URL = process.env.INTERNAL_API_URL ?? "http://localhost:8000";

export async function GET() {
  const user = await getWebUser();
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const upstream = await fetch(`${INTERNAL_API_URL}/internal/usage/summary`, {
    cache: "no-store",
  });
  return NextResponse.json(await upstream.json(), { status: upstream.status });
}
