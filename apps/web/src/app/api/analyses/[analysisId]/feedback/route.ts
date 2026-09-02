import { NextResponse } from "next/server";
import { analysisAccessTokenForUser } from "@/lib/analysis-access";
import { getWebUser } from "@/lib/web-user";
import { feedbackCollectionEnabled } from "@/lib/feedback-access";
const API = process.env.INTERNAL_API_URL ?? "http://localhost:8000";

export async function GET(_request: Request, { params }: { params: Promise<{ analysisId: string }> }) {
  const user = await getWebUser(); if (!user) return NextResponse.json({error:"Unauthorized"},{status:401});
  if (!feedbackCollectionEnabled()) return NextResponse.json({error:"feedback_disabled"},{status:404});
  const {analysisId}=await params; const token=analysisAccessTokenForUser(user.id);
  const response=await fetch(`${API}/analyses/${encodeURIComponent(analysisId)}/feedback`,{cache:"no-store",headers:{"X-Analysis-Access-Token":token}});
  return NextResponse.json(await response.json(),{status:response.status});
}
