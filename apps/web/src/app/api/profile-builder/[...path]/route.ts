import { NextResponse } from "next/server";
import { analysisAccessTokenForUser } from "@/lib/analysis-access";
import { getWebUser } from "@/lib/web-user";

const INTERNAL_API_URL = process.env.INTERNAL_API_URL ?? "http://localhost:8000";

type Context = { params: Promise<{ path: string[] }> };

function internalUrl(path: string[]) {
  return `${INTERNAL_API_URL}/profile-builder/${path.map(encodeURIComponent).join("/")}`;
}

function isOwnedJsonPath(path: string[]) {
  return path[0] === "profiles" || path[0] === "templates";
}

async function authenticatedContext(context: Context) {
  const user = await getWebUser();
  if (!user) return null;
  const { path } = await context.params;
  return {
    path,
    accessToken: analysisAccessTokenForUser(user.id),
  };
}

async function proxyOwnedJson(
  method: "GET" | "POST" | "PUT" | "DELETE",
  req: Request,
  context: Context,
) {
  const auth = await authenticatedContext(context);
  if (!auth) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  if (!isOwnedJsonPath(auth.path)) {
    return NextResponse.json({ error: "Unknown Profile Builder action" }, { status: 404 });
  }

  const headers: Record<string, string> = {
    "X-Profile-Builder-Access-Token": auth.accessToken,
  };
  let body: string | undefined;
  if (method === "POST" || method === "PUT") {
    headers["Content-Type"] = "application/json";
    body = await req.text();
  }
  const upstream = await fetch(internalUrl(auth.path), {
    method,
    headers,
    body,
    cache: "no-store",
  });
  const data = await upstream.json().catch(() => ({}));
  return NextResponse.json(data, { status: upstream.status });
}

export async function GET(req: Request, context: Context) {
  return proxyOwnedJson("GET", req, context);
}

export async function POST(req: Request, context: Context) {
  const auth = await authenticatedContext(context);
  if (!auth) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  const action = auth.path.join("/");

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

  if (action === "summary") {
    const upstream = await fetch(`${INTERNAL_API_URL}/profile-builder/summary`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-AI-Enabled": req.headers.get("X-AI-Enabled") === "false" ? "false" : "true",
      },
      body: await req.text(),
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

  if (isOwnedJsonPath(auth.path)) {
    const headers = {
      "Content-Type": "application/json",
      "X-Profile-Builder-Access-Token": auth.accessToken,
    };
    const upstream = await fetch(internalUrl(auth.path), {
      method: "POST",
      headers,
      body: await req.text(),
      cache: "no-store",
    });
    const data = await upstream.json().catch(() => ({}));
    return NextResponse.json(data, { status: upstream.status });
  }

  return NextResponse.json({ error: "Unknown Profile Builder action" }, { status: 404 });
}

export async function PUT(req: Request, context: Context) {
  return proxyOwnedJson("PUT", req, context);
}

export async function DELETE(req: Request, context: Context) {
  return proxyOwnedJson("DELETE", req, context);
}
