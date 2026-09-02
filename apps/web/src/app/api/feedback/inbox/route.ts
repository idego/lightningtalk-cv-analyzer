import { NextResponse } from "next/server";
import { feedbackRole } from "@/lib/feedback-access";
import { getWebUser } from "@/lib/web-user";
const API=process.env.INTERNAL_API_URL ?? "http://localhost:8000";
export async function GET(request:Request){const user=await getWebUser();if(!user||!feedbackRole(user.email))return NextResponse.json({error:"Forbidden"},{status:403});const query=new URL(request.url).search;const r=await fetch(`${API}/internal/feedback${query}`,{cache:"no-store"});return NextResponse.json(await r.json(),{status:r.status})}
