import fs from "node:fs";
import path from "node:path";
import Database from "better-sqlite3";
import { betterAuth } from "better-auth";

const allowedDomains = (process.env.ALLOWED_EMAIL_DOMAINS ?? "idego.io")
  .split(",")
  .map((d) => d.trim().toLowerCase())
  .filter(Boolean);

const dbPath = process.env.BETTER_AUTH_DB_PATH ?? "./data/auth.db";
fs.mkdirSync(path.dirname(dbPath), { recursive: true });

const googleClientId = process.env.GOOGLE_OAUTH_CLIENT_ID;
const googleClientSecret = process.env.GOOGLE_OAUTH_CLIENT_SECRET;

const socialProviders =
  googleClientId && googleClientSecret
    ? {
        google: {
          clientId: googleClientId,
          clientSecret: googleClientSecret,
        },
      }
    : {};

const betterAuthSecret = process.env.BETTER_AUTH_SECRET;
if (!betterAuthSecret) {
  throw new Error("BETTER_AUTH_SECRET is required");
}

export const auth = betterAuth({
  database: new Database(dbPath),
  secret: betterAuthSecret,
  baseURL: process.env.BETTER_AUTH_URL ?? process.env.BASE_URL ?? "http://localhost:3000",
  socialProviders,
  databaseHooks: {
    user: {
      create: {
        before: async (user) => {
          const email = user.email?.toLowerCase().trim();
          const emailVerified = Boolean(user.emailVerified);
          const domain = email?.split("@")[1];

          if (!email || !emailVerified || !domain || !allowedDomains.includes(domain)) {
            throw new Error("Only verified accounts from allowed domains can sign in.");
          }

          return {
            data: {
              ...user,
            },
          };
        },
      },
    },
  },
});
