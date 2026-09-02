export function sourceLabel(value: string): string {
  try {
    const hostname = new URL(value).hostname.replace(/^www\./, "");
    return hostname || value;
  } catch {
    return value;
  }
}
