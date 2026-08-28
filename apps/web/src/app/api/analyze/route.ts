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
  const files = incoming.getAll("files");
  const single = incoming.get("file");

  const payload = new FormData();
  if (single instanceof File) {
    payload.append("files", single, single.name);
  }

  for (const item of files) {
    if (item instanceof File) {
      payload.append("files", item, item.name);
    }
  }

  const hasFiles = payload.getAll("files").length > 0;
  if (!hasFiles) {
    return NextResponse.json({ error: "No files provided" }, { status: 400 });
  }

  const analysisAccessToken = analysisAccessTokenForUser(user.id);
  const upstream = await fetch(`${INTERNAL_API_URL}/analyze/batch`, {
    method: "POST",
    body: payload,
    headers: {
      "X-Analysis-Access-Token": analysisAccessToken,
      "X-Report-Language": req.headers.get("X-Report-Language") ?? "en",
      "X-AI-Enabled": req.headers.get("X-AI-Enabled") === "false" ? "false" : "true",
    },
  });

  const data = await upstream.json();
  if (Array.isArray(data.results)) {
    for (const item of data.results) {
      if (item?.status === "ok" && item.report) item.report.analysis_access_token = analysisAccessToken;
    }
  }
  return NextResponse.json(data, { status: upstream.status });
}
