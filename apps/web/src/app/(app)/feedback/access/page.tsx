import { redirect } from "next/navigation";
import { feedbackRole } from "@/lib/feedback-access";
import { requireWebUser } from "@/lib/web-user";
import { FeedbackAccess } from "@/components/feedback/feedback-access";
export default async function AccessPage(){const user=await requireWebUser();if(feedbackRole(user.id)!=="owner")redirect("/feedback");return <FeedbackAccess/>}
