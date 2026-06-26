import { headers } from "next/headers";
import { redirect } from "next/navigation";
import { auth } from "@/auth";

export type WebUser = {
  id: string;
  email: string;
  name?: string | null;
};

export async function requireWebUser(): Promise<WebUser> {
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
  const h = await headers();
  const session = await auth.api.getSession({ headers: h });
  if (!session?.user?.id || !session.user.email) return null;
  return {
    id: session.user.id,
    email: session.user.email,
    name: session.user.name,
  };
}
