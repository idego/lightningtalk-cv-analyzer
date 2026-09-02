import { NextResponse } from "next/server";
import { feedbackRole } from "@/lib/feedback-access";
import { getWebUser } from "@/lib/web-user";
const API=process.env.INTERNAL_API_URL??"http://localhost:8000";
export async function PUT(request:Request,{params}:{params:Promise<{targetId:string;actorHash:string}>}){const user=await getWebUser();if(!user||!feedbackRole(user.email))return NextResponse.json({error:"Forbidden"},{status:403});const {targetId,actorHash}=await params;const body=await request.text();if(body.length>2048)return NextResponse.json({error:"Request too large"},{status:413});const r=await fetch(`${API}/internal/feedback/${encodeURIComponent(targetId)}/${encodeURIComponent(actorHash)}/triage`,{method:"PUT",headers:{"Content-Type":"application/json","X-Feedback-Maintainer":user.id},body});return NextResponse.json(await r.json(),{status:r.status})}
