import { NextResponse } from "next/server";

const INTERNAL_API_URL = process.env.INTERNAL_API_URL ?? "http://localhost:8000";

type ApiHealth = { ready?: unknown };

export async function GET() {
  try {
    const upstream = await fetch(`${INTERNAL_API_URL}/health`, { cache: "no-store" });
    const payload = (await upstream.json()) as ApiHealth;
    const ready = upstream.ok && payload.ready === true;
    return NextResponse.json(
      { status: ready ? "ready" : "degraded", ready },
      { status: ready ? 200 : 503, headers: { "Cache-Control": "no-store" } },
    );
  } catch {
    return NextResponse.json(
      { status: "unavailable", ready: false },
      { status: 503, headers: { "Cache-Control": "no-store" } },
    );
  }
}
