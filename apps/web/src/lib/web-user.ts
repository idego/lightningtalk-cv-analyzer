import { headers } from "next/headers";
import { redirect } from "next/navigation";
import { auth } from "@/auth";
import { isLocalDevAuthBypassEnabled } from "@/lib/local-dev-auth";

export type WebUser = {
  id: string;
  email: string;
  name?: string | null;
};

const localDevUser: WebUser = {
  id: "local-dev-user",
  email: "local-dev@localhost",
  name: "Local developer",
};

export async function requireWebUser(): Promise<WebUser> {
  if (isLocalDevAuthBypassEnabled()) return localDevUser;

  const h = await headers();
  const session = await auth.api.getSession({ headers: h });

  if (!session?.user?.id || !session.user.email) {
    redirect("/sign-in");
  }

  return {
    id: session.user.id,
    email: session.user.email,
    name: session.user.name,
  };
}

export async function getWebUser(): Promise<WebUser | null> {
  if (isLocalDevAuthBypassEnabled()) return localDevUser;

  const h = await headers();
  const session = await auth.api.getSession({ headers: h });
  if (!session?.user?.id || !session.user.email) return null;
  return {
    id: session.user.id,
    email: session.user.email,
    name: session.user.name,
  };
}
