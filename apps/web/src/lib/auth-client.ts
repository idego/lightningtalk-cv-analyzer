"use client";

import { createAuthClient } from "better-auth/react";

export const authClient = createAuthClient({
  baseURL: typeof window !== "undefined"
    ? ""
    : process.env.BETTER_AUTH_URL ?? process.env.BASE_URL ?? "http://localhost:3000",
});
