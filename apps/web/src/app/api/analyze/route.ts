import { headers } from "next/headers";
import { NextResponse } from "next/server";
import { auth } from "@/auth";

const INTERNAL_API_URL = process.env.INTERNAL_API_URL ?? "http://localhost:8000";

export async function POST(req: Request) {
  const h = await headers();
  const session = await auth.api.getSession({ headers: h });

  if (!session?.user?.id) {
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

  const upstream = await fetch(`${INTERNAL_API_URL}/analyze/batch`, {
    method: "POST",
    body: payload,
  });

  const data = await upstream.json();
  return NextResponse.json(data, { status: upstream.status });
}
