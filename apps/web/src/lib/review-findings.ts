import type { AIAnalysis, ReviewFlag } from "@/lib/analyze-types";

export function partitionReviewFlags(flags: ReviewFlag[]) {
  return {
    attention: flags.filter((flag) => flag.importance === "attention"),
    worthKnowing: flags.filter((flag) => flag.importance === "worth_knowing"),
    remaining: flags.filter((flag) => flag.importance === "remaining"),
  };
}

export function aiStatusMessage(
  status: AIAnalysis["status"],
  reason: AIAnalysis["failure_reason"],
) {
  if (status === "disabled") {
    return "Analiza AI jest wyłączona. Raport zawiera tylko sygnały sprawdzone kodem.";
  }
  if (status === "failed" && reason === "refusal") {
    return "Model odmówił analizy tego dokumentu. Raport deterministyczny nadal jest dostępny.";
  }
  if (status === "failed") {
    return "Nie udało się wykonać analizy AI. Raport deterministyczny nadal jest dostępny.";
  }
  return null;
}
