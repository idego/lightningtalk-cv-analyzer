import { NextResponse } from "next/server";
import { fetchInternalJson } from "@/lib/internal-api";
import { getWebUser } from "@/lib/web-user";

export async function GET() {
  if (!(await getWebUser())) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  const result = await fetchInternalJson("/health", { cache: "no-store" });
  if (!result.ok && result.status === 502) {
    return NextResponse.json(
      { status: "unavailable", ready: false, capabilities: {} },
      { status: 503 },
    );
  }
  return NextResponse.json(result.payload, { status: result.status });
}
