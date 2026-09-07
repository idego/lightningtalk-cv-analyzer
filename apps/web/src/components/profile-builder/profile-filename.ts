export function profileFilename(pattern: string, first: string, last: string, template: string, extension: "pdf" | "docx") {
  const name = [first.trim(), last.trim()].filter(Boolean).join(" ") || "candidate";
  const date = new Intl.DateTimeFormat("en-CA", { year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date());
  const rendered = pattern
    .replaceAll("{name}", name)
    .replaceAll("{first_name}", first.trim())
    .replaceAll("{last_name}", last.trim())
    .replaceAll("{template}", template)
    .replaceAll("{date}", date)
    .replace(/[^\p{L}\p{N}._ -]+/gu, "-")
    .replace(/\s+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^[._-]+|[._-]+$/g, "")
    .toLowerCase();
  return `${rendered || "candidate-profile"}.${extension}`;
}
