import { NextResponse } from "next/server";
import { analysisAccessTokenForUser } from "@/lib/analysis-access";
import { getWebUser } from "@/lib/web-user";

const INTERNAL_API_URL = process.env.INTERNAL_API_URL ?? "http://localhost:8000";

export async function POST(req: Request) {
  const user = await getWebUser();
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const requestId = req.headers.get("X-Analysis-Request-Id");
  if (!requestId) return NextResponse.json({ error: "Missing request id" }, { status: 400 });

  const upstream = await fetch(`${INTERNAL_API_URL}/analyze/cancel`, {
    method: "POST",
    headers: {
      "X-Analysis-Access-Token": analysisAccessTokenForUser(user.id),
      "X-Analysis-Request-Id": requestId,
    },
  });
  const data = await upstream.json().catch(() => ({}));
  return NextResponse.json(data, { status: upstream.status });
}
