import { NextResponse } from "next/server";
import { getWebUser } from "@/lib/web-user";

const INTERNAL_API_URL = process.env.INTERNAL_API_URL ?? "http://localhost:8000";

export async function GET() {
  if (!(await getWebUser())) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  try {
    const upstream = await fetch(`${INTERNAL_API_URL}/health`, { cache: "no-store" });
    return NextResponse.json(await upstream.json(), { status: upstream.status });
  } catch {
    return NextResponse.json({ status: "unavailable", ready: false, capabilities: {} }, { status: 503 });
  }
}
