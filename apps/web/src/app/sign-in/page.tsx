import { redirect } from "next/navigation";
import { getWebUser } from "@/lib/web-user";
import { GoogleSignInCard } from "@/components/auth/google-sign-in-card";

export default async function SignInPage() {
  const user = await getWebUser();
  if (user) {
    redirect("/analyze");
  }

  return (
    <div className="flex min-h-dvh items-center justify-center px-4 py-10">
      <GoogleSignInCard />
    </div>
  );
}
