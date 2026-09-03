import { NextResponse } from "next/server";
import { analysisAccessTokenForUser } from "@/lib/analysis-access";
import { getWebUser } from "@/lib/web-user";

const INTERNAL_API_URL = process.env.INTERNAL_API_URL ?? "http://localhost:8000";

export async function POST(req: Request) {
  const user = await getWebUser();

  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const incoming = await req.formData();
  const file = incoming.get("file") ?? incoming.getAll("files")[0];
  if (!(file instanceof File)) {
    return NextResponse.json({ error: "No file provided" }, { status: 400 });
  }

  const payload = new FormData();
  payload.append("file", file, file.name);

  const analysisAccessToken = analysisAccessTokenForUser(user.id);
  const upstream = await fetch(`${INTERNAL_API_URL}/analyze`, {
    method: "POST",
    body: payload,
    headers: {
      "X-Analysis-Access-Token": analysisAccessToken,
      "X-Report-Language": req.headers.get("X-Report-Language") ?? "en",
    },
  });

  const data = await upstream.json();
  if (upstream.ok && data && typeof data === "object") data.analysis_access_token = analysisAccessToken;
  return NextResponse.json(data, { status: upstream.status });
}
