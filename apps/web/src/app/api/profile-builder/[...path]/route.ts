import { NextResponse } from "next/server";
import { analysisAccessTokenForUser } from "@/lib/analysis-access";
import { getWebUser } from "@/lib/web-user";

const INTERNAL_API_URL = process.env.INTERNAL_API_URL ?? "http://localhost:8000";
const PROFILE_BUILDER_MAX_BYTES = 10 * 1024 * 1024;

type Context = { params: Promise<{ path: string[] }> };
type AuthenticatedProfileBuilderContext = { path: string[]; accessToken: string };
type HttpMethod = "GET" | "POST" | "PUT" | "DELETE";

function internalUrl(path: string[]) {
  return `${INTERNAL_API_URL}/profile-builder/${path.map(encodeURIComponent).join("/")}`;
}

function isCrudPath(path: string[]) {
  return ["profiles", "templates", "preferences", "custom-fields"].includes(path[0] ?? "");
}

async function authenticatedContext(context: Context): Promise<AuthenticatedProfileBuilderContext | null> {
  const user = await getWebUser();
  if (!user) return null;
  const { path } = await context.params;
  return { path, accessToken: analysisAccessTokenForUser(user.id) };
}

function upstreamHeaders(accessToken: string, extra?: Record<string, string>) {
  return {
    "X-Profile-Builder-Access-Token": accessToken,
    ...extra,
  };
}

async function jsonResponse(upstream: Response) {
  const data = await upstream.json().catch(() => ({}));
  return NextResponse.json(data, { status: upstream.status });
}

async function proxyCrud(
  method: HttpMethod,
  req: Request,
  context: Context,
) {
  const auth = await authenticatedContext(context);
  if (!auth) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  if (!isCrudPath(auth.path)) {
    return NextResponse.json({ error: "Unknown Profile Builder action" }, { status: 404 });
  }

  const hasJsonBody = method === "POST" || method === "PUT";
  const upstream = await fetch(internalUrl(auth.path), {
    method,
    headers: upstreamHeaders(
      auth.accessToken,
      hasJsonBody ? { "Content-Type": "application/json" } : undefined,
    ),
    body: hasJsonBody ? await req.text() : undefined,
    cache: "no-store",
  });
  return jsonResponse(upstream);
}

async function proxyJsonAction(
  auth: AuthenticatedProfileBuilderContext,
  req: Request,
  action: "summary" | "transform",
) {
  const upstream = await fetch(`${INTERNAL_API_URL}/profile-builder/${action}`, {
    method: "POST",
    headers: upstreamHeaders(auth.accessToken, {
      "Content-Type": "application/json",
      "X-AI-Enabled": req.headers.get("X-AI-Enabled") === "false" ? "false" : "true",
    }),
    body: await req.text(),
  });
  return jsonResponse(upstream);
}

async function proxyExport(
  auth: AuthenticatedProfileBuilderContext,
  req: Request,
  format: "pdf" | "docx",
) {
  const upstream = await fetch(`${INTERNAL_API_URL}/profile-builder/export/${format}`, {
    method: "POST",
    headers: upstreamHeaders(auth.accessToken, { "Content-Type": "application/json" }),
    body: await req.text(),
  });
  if (!upstream.ok) return jsonResponse(upstream);

  const fallbackContentType = format === "pdf"
    ? "application/pdf"
    : "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
  return new Response(await upstream.arrayBuffer(), {
    status: upstream.status,
    headers: {
      "Content-Type": upstream.headers.get("Content-Type") ?? fallbackContentType,
      "Content-Disposition": upstream.headers.get("Content-Disposition")
        ?? `attachment; filename="candidate-profile.${format}"`,
    },
  });
}

export async function GET(req: Request, context: Context) {
  return proxyCrud("GET", req, context);
}

export async function POST(req: Request, context: Context) {
  const auth = await authenticatedContext(context);
  if (!auth) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  const action = auth.path.join("/");

  if (action === "extract") {
    const incoming = await req.formData();
    const file = incoming.get("file");
    if (!(file instanceof File)) {
      return NextResponse.json({ error: "No file provided" }, { status: 400 });
    }
    if (file.size > PROFILE_BUILDER_MAX_BYTES) {
      return NextResponse.json(
        { detail: "profile_builder_file_size_limit_exceeded" },
        { status: 413 },
      );
    }
    const form = new FormData();
    form.append("file", file, file.name);
    const upstream = await fetch(`${INTERNAL_API_URL}/profile-builder/extract`, {
      method: "POST",
      body: form,
      headers: upstreamHeaders(auth.accessToken, {
        "X-AI-Enabled": req.headers.get("X-AI-Enabled") === "false" ? "false" : "true",
      }),
    });
    return jsonResponse(upstream);
  }

  if (action === "summary" || action === "transform") {
    return proxyJsonAction(auth, req, action);
  }
  if (action === "export/pdf") return proxyExport(auth, req, "pdf");
  if (action === "export/docx") return proxyExport(auth, req, "docx");

  if (isCrudPath(auth.path)) {
    const upstream = await fetch(internalUrl(auth.path), {
      method: "POST",
      headers: upstreamHeaders(auth.accessToken, { "Content-Type": "application/json" }),
      body: await req.text(),
      cache: "no-store",
    });
    return jsonResponse(upstream);
  }

  return NextResponse.json({ error: "Unknown Profile Builder action" }, { status: 404 });
}

export async function PUT(req: Request, context: Context) {
  return proxyCrud("PUT", req, context);
}

export async function DELETE(req: Request, context: Context) {
  return proxyCrud("DELETE", req, context);
}
