import { NextResponse } from "next/server";
import { fetchInternalJson } from "@/lib/internal-api";

type ApiHealth = { ready?: unknown };

export async function GET() {
  const result = await fetchInternalJson("/health", { cache: "no-store" });
  if (!result.ok || typeof result.payload !== "object" || result.payload === null) {
    return NextResponse.json(
      { status: "unavailable", ready: false },
      { status: 503, headers: { "Cache-Control": "no-store" } },
    );
  }
  const payload = result.payload as ApiHealth;
  const ready = result.status < 400 && payload.ready === true;
  return NextResponse.json(
    { status: ready ? "ready" : "degraded", ready },
    { status: ready ? 200 : 503, headers: { "Cache-Control": "no-store" } },
  );
}
