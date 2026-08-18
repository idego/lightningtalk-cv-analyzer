const LOCAL_HOSTNAMES = new Set(["localhost", "127.0.0.1", "::1"]);

export function isLocalDevAuthBypassEnabled(): boolean {
  if (process.env.LOCAL_DEV_AUTH_BYPASS !== "true") return false;

  const baseUrl = process.env.BASE_URL ?? process.env.BETTER_AUTH_URL;
  if (!baseUrl) return false;

  try {
    return LOCAL_HOSTNAMES.has(new URL(baseUrl).hostname);
  } catch {
    return false;
  }
}
