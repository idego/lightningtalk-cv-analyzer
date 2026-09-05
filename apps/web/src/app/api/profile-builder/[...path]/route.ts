import { NextResponse } from "next/server";
import { analysisAccessTokenForUser } from "@/lib/analysis-access";
import { getWebUser } from "@/lib/web-user";
import { ProfileBodyTooLarge, readProfileBody } from "@/lib/profile-request-body";

const INTERNAL_API_URL = process.env.INTERNAL_API_URL ?? "http://localhost:8000";
const MAX_FILE_BYTES = 10 * 1024 * 1024;
const MAX_JSON_BYTES = 4 * 1024 * 1024;
const privateHeaders = { "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff" };
type Context = { params: Promise<{ path: string[] }> };

async function proxy(request: Request, context: Context) {
  const user = await getWebUser();
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401, headers: privateHeaders });
  const { path } = await context.params;
  const action = path.join("/");
  const validCrud = path.length <= 2 && ["profiles", "templates", "preferences", "custom-fields"].includes(path[0] ?? "");
  const validAction = request.method === "POST" && ["extract", "summary", "transform", "export/pdf", "export/docx"].includes(action);
  if (!validCrud && !validAction) return NextResponse.json({ error: "Unknown Profile Builder action" }, { status: 404, headers: privateHeaders });

  try {
    const headers: Record<string, string> = { "X-Profile-Builder-Access-Token": analysisAccessTokenForUser(user.id) };
    let body: BodyInit | undefined;
    if (request.method === "POST" || request.method === "PUT") {
      if (action === "extract") {
        const bytes = await readProfileBody(request, MAX_FILE_BYTES + 128 * 1024);
        let form: FormData;
        try { form = await new Response(bytes, { headers: { "Content-Type": request.headers.get("content-type") ?? "" } }).formData(); }
        catch { return NextResponse.json({ error: "Invalid upload" }, { status: 400, headers: privateHeaders }); }
        const file = form.get("file");
        if (!(file instanceof File)) return NextResponse.json({ error: "No file provided" }, { status: 400, headers: privateHeaders });
        if (file.size > MAX_FILE_BYTES) throw new ProfileBodyTooLarge();
        const outgoing = new FormData();
        outgoing.append("file", file, file.name);
        body = outgoing;
      } else {
        const bytes = await readProfileBody(request, MAX_JSON_BYTES);
        const text = new TextDecoder().decode(bytes);
        try { JSON.parse(text); } catch { return NextResponse.json({ error: "Invalid JSON" }, { status: 400, headers: privateHeaders }); }
        body = text;
        headers["Content-Type"] = "application/json";
      }
    }
    if (["extract", "summary", "transform"].includes(action)) headers["X-AI-Enabled"] = request.headers.get("X-AI-Enabled") === "false" ? "false" : "true";
    const upstream = await fetch(`${INTERNAL_API_URL}/profile-builder/${path.map(encodeURIComponent).join("/")}`, {
      method: request.method, body, headers, cache: "no-store", signal: request.signal,
    });
    if (upstream.ok && action.startsWith("export/")) {
      return new Response(upstream.body, { status: upstream.status, headers: {
        ...privateHeaders,
        "Content-Type": upstream.headers.get("Content-Type") ?? "application/octet-stream",
        "Content-Disposition": upstream.headers.get("Content-Disposition") ?? 'attachment; filename="candidate-profile"',
      } });
    }
    return NextResponse.json(await upstream.json().catch(() => ({ error: "Invalid service response" })), { status: upstream.status, headers: privateHeaders });
  } catch (cause) {
    if (cause instanceof ProfileBodyTooLarge) return NextResponse.json({ detail: action === "extract" ? "profile_builder_file_size_limit_exceeded" : "profile_builder_request_too_large" }, { status: 413, headers: privateHeaders });
    return NextResponse.json({ error: "Profile Builder is temporarily unavailable" }, { status: 503, headers: privateHeaders });
  }
}

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const DELETE = proxy;
