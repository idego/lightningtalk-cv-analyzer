import { NextResponse } from "next/server";
import {
  analysisOwnerHeaders,
  INTERNAL_API_URL,
} from "@/lib/internal-api";
import { getWebUser } from "@/lib/web-user";

const REPORT_LANGUAGES = new Set(["en", "pl"]);

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

  const reportLanguage = (req.headers.get("X-Report-Language") ?? "en")
    .trim()
    .toLowerCase();
  if (!REPORT_LANGUAGES.has(reportLanguage)) {
    return NextResponse.json(
      { error: "unsupported_report_language" },
      { status: 400 },
    );
  }

  const payload = new FormData();
  payload.append("file", file, file.name);
  const requestId = req.headers.get("X-Analysis-Request-Id");

  let upstream: Response;
  try {
    upstream = await fetch(`${INTERNAL_API_URL}/analyze`, {
      method: "POST",
      body: payload,
      headers: {
        ...analysisOwnerHeaders(user.id),
        "X-Report-Language": reportLanguage,
        ...(requestId ? { "X-Analysis-Request-Id": requestId } : {}),
      },
    });
  } catch {
    return NextResponse.json({ error: "upstream_unavailable" }, { status: 502 });
  }

  const text = await upstream.text().catch(() => "");
  if (!text) return NextResponse.json({}, { status: upstream.status });
  try {
    return NextResponse.json(JSON.parse(text), { status: upstream.status });
  } catch {
    return NextResponse.json(
      { error: "upstream_invalid_response" },
      { status: upstream.ok ? 502 : upstream.status },
    );
  }
}
