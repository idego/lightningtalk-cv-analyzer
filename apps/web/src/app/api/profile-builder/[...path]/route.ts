import { NextResponse } from "next/server";
import { getWebUser } from "@/lib/web-user";

const INTERNAL_API_URL = process.env.INTERNAL_API_URL ?? "http://localhost:8000";

export async function POST(
  req: Request,
  context: { params: Promise<{ path: string[] }> },
) {
  const user = await getWebUser();
  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { path } = await context.params;
  const action = path.join("/");

  if (action === "extract") {
    const incoming = await req.formData();
    const file = incoming.get("file");
    if (!(file instanceof File)) {
      return NextResponse.json({ error: "No file provided" }, { status: 400 });
    }
    const form = new FormData();
    form.append("file", file, file.name);
    const upstream = await fetch(`${INTERNAL_API_URL}/profile-builder/extract`, {
      method: "POST",
      body: form,
      headers: {
        "X-AI-Enabled": req.headers.get("X-AI-Enabled") === "false" ? "false" : "true",
      },
    });
    const data = await upstream.json().catch(() => ({}));
    return NextResponse.json(data, { status: upstream.status });
  }

  if (action === "export/docx") {
    const upstream = await fetch(`${INTERNAL_API_URL}/profile-builder/export/docx`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: await req.text(),
    });
    if (!upstream.ok) {
      const data = await upstream.json().catch(() => ({}));
      return NextResponse.json(data, { status: upstream.status });
    }
    return new Response(await upstream.arrayBuffer(), {
      status: upstream.status,
      headers: {
        "Content-Type": upstream.headers.get("Content-Type") ?? "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "Content-Disposition": upstream.headers.get("Content-Disposition") ?? 'attachment; filename="candidate-profile.docx"',
      },
    });
  }

  return NextResponse.json({ error: "Unknown Profile Builder action" }, { status: 404 });
}
