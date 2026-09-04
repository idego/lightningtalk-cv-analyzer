import { redirect } from "next/navigation";
import { feedbackRole } from "@/lib/feedback-access";
import { requireWebUser } from "@/lib/web-user";
import { FeedbackInbox } from "@/components/feedback/feedback-inbox";
export default async function FeedbackPage(){const user=await requireWebUser();const role=feedbackRole(user.email);if(!role)redirect("/analyze");return <FeedbackInbox owner={role==="owner"}/>}
