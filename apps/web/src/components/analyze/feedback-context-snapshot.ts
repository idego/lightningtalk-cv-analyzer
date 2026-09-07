export type FeedbackContextSnapshot = {
  contextLabel: string | null;
  contextText: string | null;
};

export function captureFeedbackContext(
  anchor: HTMLElement | null,
): FeedbackContextSnapshot {
  const contextElement = anchor?.closest<HTMLElement>("[data-feedback-snapshot]");
  const contextLabel = contextElement?.dataset.feedbackSnapshot?.trim() || null;
  const contextClone = contextElement?.cloneNode(true) as HTMLElement | undefined;
  contextClone
    ?.querySelectorAll("[data-feedback-target]")
    .forEach((control) => control.remove());
  const contextText = contextClone?.innerText.trim().slice(0, 12_000) || null;
  return { contextLabel, contextText };
}
