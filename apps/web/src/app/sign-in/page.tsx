import { redirect } from "next/navigation";
import Login07 from "@/components/login-07";
import { SiteFooter } from "@/components/layout/site-footer";
import { isLocalDevAuthBypassEnabled } from "@/lib/local-dev-auth";

export default function SignInPage() {
  if (isLocalDevAuthBypassEnabled()) redirect("/analyze");

  return (
    <div className="flex min-h-dvh flex-col">
      <Login07 />
      <SiteFooter />
    </div>
  );
}
