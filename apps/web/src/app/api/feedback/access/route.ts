import { NextResponse } from "next/server";
import { feedbackRole,grantFeedbackAccess,listFeedbackMembers,revokeFeedbackAccess } from "@/lib/feedback-access";
import { getWebUser } from "@/lib/web-user";
async function owner(){const user=await getWebUser();return user&&feedbackRole(user.id)==="owner"?user:null}
export async function GET(){const user=await owner();return user?NextResponse.json({members:listFeedbackMembers()}):NextResponse.json({error:"Forbidden"},{status:403})}
export async function PUT(request:Request){const user=await owner();if(!user)return NextResponse.json({error:"Forbidden"},{status:403});const body=await request.json();if(typeof body.email!=="string"||!(body.role==="owner"||body.role==="reviewer"))return NextResponse.json({error:"Invalid request"},{status:422});try{return NextResponse.json({userId:grantFeedbackAccess(body.email,body.role,user.id)})}catch(error){return NextResponse.json({error:error instanceof Error?error.message:"Invalid request"},{status:422})}}
export async function DELETE(request:Request){const user=await owner();if(!user)return NextResponse.json({error:"Forbidden"},{status:403});const body=await request.json();try{return NextResponse.json({revoked:revokeFeedbackAccess(String(body.userId??""))})}catch(error){return NextResponse.json({error:error instanceof Error?error.message:"Invalid request"},{status:409})}}
