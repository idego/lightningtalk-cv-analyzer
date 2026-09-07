"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import type { AnalysisReport } from "@/lib/analyze-types";
import type { FeedbackResponse, FeedbackTarget } from "@/lib/feedback-types";
import { useCopy } from "@/lib/app-settings";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { captureFeedbackContext } from "./feedback-context-snapshot";
import { feedbackMorphPath } from "./feedback-control-motion";
import { submitFeedback, type FeedbackSubmissionBody } from "./feedback-submission";
import "./feedback-control.css";
type Rating = "helpful" | "not_helpful" | null;
type Phase =
  | "idle"
  | "open"
  | "collapsing"
  | "launching"
  | "delivered"
  | "resetting";
export function FeedbackControl({
  analysisId,
  target,
  report,
  failure = false,
}: {
  analysisId: string;
  target: FeedbackTarget;
  report?: AnalysisReport;
  failure?: boolean;
}) {
  const { t } = useCopy();
  const [phase, setPhase] = useState<Phase>("idle"),
    [rating, setRating] = useState<Rating>(
      failure ? "not_helpful" : (target.response?.rating ?? null),
    ),
    [comment, setComment] = useState(target.response?.comment ?? ""),
    [confirmed, setConfirmed] = useState<FeedbackResponse | null>(target.response),
    [error, setError] = useState(false),
    [height, setHeight] = useState(36);
  const anchor = useRef<HTMLDivElement>(null),
    cloud = useRef<HTMLDivElement>(null),
    trigger = useRef<HTMLButtonElement>(null),
    editor = useRef<HTMLTextAreaElement>(null),
    path = useRef<SVGPathElement>(null),
    progress = useRef(0),
    frame = useRef<number | null>(null),
    timers = useRef<number[]>([]),
    lastWidth = useRef(0),
    openingUntil = useRef(0);
  const draftKey = `cv-feedback-draft:${analysisId}:${target.target_id}`,
    open = phase === "open",
    sending = ["collapsing", "launching", "delivered", "resetting"].includes(
      phase,
    ),
    normalized = comment.trim().replace(/\s+/g, " "),
    valid =
      failure ||
      rating !== null ||
      (normalized.length > 0 && normalized.length <= 180),
    disabledReason = t("feedbackSelectionRequired");
  const draw = useCallback((value: number) => {
    path.current?.setAttribute("d", feedbackMorphPath(value));
  }, []);
  const morph = useCallback(
    (targetValue: number) => {
      if (frame.current) cancelAnimationFrame(frame.current);
      if (matchMedia("(prefers-reduced-motion: reduce)").matches) {
        progress.current = targetValue;
        draw(targetValue);
        return;
      }
      const from = progress.current,
        start = performance.now(),
        duration = 180 * Math.max(0.35, Math.abs(targetValue - from));
      const tick = (now: number) => {
        const time = Math.min(1, (now - start) / duration),
          eased = 1 - Math.pow(1 - time, 4);
        progress.current = from + (targetValue - from) * eased;
        draw(progress.current);
        if (time < 1) frame.current = requestAnimationFrame(tick);
      };
      frame.current = requestAnimationFrame(tick);
    },
    [draw],
  );
  const resize = useCallback((measureWidth?: number) => {
    if (!editor.current) return;
    const previousWidth = editor.current.style.width;
    if (measureWidth) editor.current.style.width = `${measureWidth}px`;
    editor.current.style.height = "36px";
    const next = Math.min(126, Math.max(36, editor.current.scrollHeight));
    if (measureWidth) editor.current.style.width = previousWidth;
    editor.current.style.height = `${next}px`;
    setHeight(next);
  }, []);
  const close = useCallback(() => {
    if (sending) return;
    setPhase("idle");
    morph(0);
    requestAnimationFrame(() => trigger.current?.focus());
  }, [morph, sending]);
  useEffect(() => {
    const draft = sessionStorage.getItem(draftKey);
    if (!draft || target.response?.comment) return;
    const timer = window.setTimeout(() => setComment(draft), 0);
    return () => clearTimeout(timer);
  }, [draftKey, target.response?.comment]);
  useEffect(() => {
    if (comment) sessionStorage.setItem(draftKey, comment);
    else sessionStorage.removeItem(draftKey);
    if (phase === "idle") resize(200);
    else if (phase === "open" && performance.now() >= openingUntil.current)
      resize();
  }, [comment, draftKey, phase, resize]);
  useEffect(() => {
    if (!editor.current) return;
    const observer = new ResizeObserver((entries) => {
      const width = entries[0].contentRect.width;
      if (Math.abs(width - lastWidth.current) < 0.25) return;
      lastWidth.current = width;
      if (performance.now() < openingUntil.current) return;
      resize();
    });
    observer.observe(editor.current);
    return () => observer.disconnect();
  }, [resize]);
  useEffect(() => {
    if (!open) return;
    const outside = (event: PointerEvent) => {
        if (!anchor.current?.contains(event.target as Node) && !cloud.current?.contains(event.target as Node)) close();
      },
      key = (event: KeyboardEvent) => {
        if (event.key === "Escape") close();
      };
    document.addEventListener("pointerdown", outside);
    document.addEventListener("keydown", key);
    return () => {
      document.removeEventListener("pointerdown", outside);
      document.removeEventListener("keydown", key);
    };
  }, [close, open]);
  useEffect(
    () => () => {
      timers.current.forEach(clearTimeout);
      if (frame.current) cancelAnimationFrame(frame.current);
    },
    [],
  );
  function toggle() {
    if (sending) return;
    if (!open) {
      resize(200);
      openingUntil.current = performance.now() + 260;
      later(() => resize(), 270);
    }
    setPhase(open ? "idle" : "open");
    morph(open ? 0 : 1);
    if (!open) requestAnimationFrame(() => editor.current?.focus());
  }
  function select(next: Rating) {
    setRating((current) => (current === next ? null : next));
    setError(false);
  }
  function later(fn: () => void, delay: number) {
    timers.current.push(window.setTimeout(fn, delay));
  }
  async function send() {
    if (!valid || sending) return;
    setError(false);
    const { contextLabel, contextText } = captureFeedbackContext(anchor.current);
    const body: FeedbackSubmissionBody = failure
      ? {
          rating: "not_helpful",
          reason: "operation_failed",
          comment: normalized || null,
          context_label: contextLabel,
          context_text: contextText,
          context_report: report ?? null,
        }
      : {
          rating,
          reason: rating === "not_helpful" ? "other" : null,
          comment: normalized || null,
          context_label: contextLabel,
          context_text: contextText,
          context_report: report ?? null,
        };
    try {
      setConfirmed(await submitFeedback({
        analysisId,
        targetId: target.target_id,
        body,
      }));
      sessionStorage.removeItem(draftKey);
      const sendRect = cloud.current
          ?.querySelector<HTMLButtonElement>(".feedback-send")
          ?.getBoundingClientRect(),
        triggerRect = trigger.current?.getBoundingClientRect();
      if (sendRect && triggerRect && cloud.current) {
        cloud.current.style.setProperty(
          "--send-from-x",
          `${sendRect.left + sendRect.width / 2 - (triggerRect.left + triggerRect.width / 2)}px`,
        );
        cloud.current.style.setProperty(
          "--send-from-y",
          `${sendRect.top + sendRect.height / 2 - (triggerRect.top + triggerRect.height / 2)}px`,
        );
      }
      setPhase("collapsing");
      later(() => setPhase("launching"), 260);
      later(() => setPhase("delivered"), 400);
      later(() => {
        setPhase("resetting");
        morph(0);
        setRating(failure ? "not_helpful" : null);
        setComment("");
      }, 1150);
      later(() => setPhase("idle"), 1390);
    } catch {
      setError(true);
    }
  }
  const remaining = 180 - comment.length,
    counterOpacity = Math.max(0, Math.min(1, (comment.length - 90) / 90)),
    classes = ["feedback-cloud", phase, confirmed ? "has-response" : ""]
      .filter(Boolean)
      .join(" ");
  return (
    <div
      ref={anchor}
      className="feedback-anchor"
      data-feedback-target={target.target_id}
    >
      <div
        ref={cloud}
        className={classes}
        style={{
          "--comment-h": `${height}px`,
        } as React.CSSProperties}
      >
        <Tooltip disabled={open || sending}>
          <TooltipTrigger render={<button
            ref={trigger}
            className="feedback-trigger"
            type="button"
            onClick={toggle}
            aria-label={open ? t("closeFeedback") : failure ? t("reportProblem") : t("rateResult")}
            aria-expanded={open}
          >
            <svg className="feedback-morph-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path ref={path} d="M13 2L17 2.8L20 5.5L22 9L21.5 13L19 16.5L15 18L11 18M11 18L8 20L8.5 17.2L5.5 15L4 11L4.8 7L7 4L13 2" />
            </svg>
          </button>} />
          <TooltipContent>{failure ? t("reportProblem") : t("giveFeedback")}</TooltipContent>
        </Tooltip>
        <section
          className="feedback-panel"
          aria-label={t("resultFeedback")}
          aria-hidden={!open}
        >
          {!failure ? (
            <div className="feedback-actions">
              <button
                className={`feedback-vote ${rating === "helpful" ? "selected" : ""}`}
                type="button"
                onClick={() => select("helpful")}
                aria-label={t("helpful")}
                aria-pressed={rating === "helpful"}
              >
                <Thumb up />
              </button>
              <button
                className={`feedback-vote ${rating === "not_helpful" ? "selected" : ""}`}
                type="button"
                onClick={() => select("not_helpful")}
                aria-label={t("needsImprovement")}
                aria-pressed={rating === "not_helpful"}
              >
                <Thumb />
              </button>
            </div>
          ) : (
            <div className="feedback-actions feedback-failure-label">
              {t("reportProblem")}
            </div>
          )}
          <div className="feedback-comment-wrap">
            <textarea
              ref={editor}
              className="feedback-editor"
              rows={1}
              value={comment}
              maxLength={180}
              placeholder={
                rating === "not_helpful" ? t("whatToImprove") : t("writeFeedback")
              }
              onChange={(event) =>
                setComment(event.target.value.replace(/\s*\n+\s*/g, " "))
              }
              onKeyDown={(event) => {
                if (event.key !== "Enter" || event.nativeEvent.isComposing)
                  return;
                event.preventDefault();
                if ((event.ctrlKey || event.metaKey) && valid) void send();
              }}
              aria-label={t("feedbackComment")}
            />
            <span
              className="feedback-counter"
              style={{ opacity: counterOpacity }}
            >
              {remaining}
            </span>
            <Tooltip disabled={valid || sending}>
              <TooltipTrigger
                render={
                  <span className="feedback-send-tooltip-trigger">
                    <button
                      className="feedback-send"
                      type="button"
                      disabled={!valid || sending}
                      onClick={() => void send()}
                      aria-label={t("sendFeedback")}
                      aria-keyshortcuts="Control+Enter Meta+Enter"
                    >
                      <Plane />
                    </button>
                  </span>
                }
              />
              <TooltipContent>{disabledReason}</TooltipContent>
            </Tooltip>
          </div>
          {error ? (
            <span className="feedback-error">{t("feedbackSaveFailed")}</span>
          ) : null}
        </section>
        <div className="feedback-send-stage" role="status">
          <Plane className="feedback-stage-plane" />
          <span className="feedback-sent-tooltip">{t("feedbackSent")}</span>
        </div>
      </div>
    </div>
  );
}
function Plane({ className = "" }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.9"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="m4 4 16 8-16 8 3-8-3-8Z" />
      <path d="M7 12h13" />
    </svg>
  );
}
function Thumb({ up = false }: { up?: boolean }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {up ? (
        <path d="M7 10v10H4V10h3Zm0 9h10.5a2 2 0 0 0 2-1.7l1-6A2 2 0 0 0 18.5 9H15l.6-3.1A2.4 2.4 0 0 0 13.2 3L8 10" />
      ) : (
        <path d="M7 14V4H4v10h3Zm0-9h10.5a2 2 0 0 1 2 1.7l1 6a2 2 0 0 1-2 2.3H15l.6 3.1a2.4 2.4 0 0 1-2.4 2.9L8 14" />
      )}
    </svg>
  );
}
