"use client";
import { useCallback, useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import type { FeedbackResponse, FeedbackTarget } from "@/lib/feedback-types";
import "./feedback-control.css";
type Rating = "helpful" | "not_helpful" | null;
type Phase =
  | "idle"
  | "open"
  | "collapsing"
  | "launching"
  | "delivered"
  | "resetting";
const B = [
    [
      [13, 2],
      [17, 2.8],
      [20, 5.5],
      [22, 9],
      [21.5, 13],
      [19, 16.5],
      [15, 18],
      [11, 18],
    ],
    [
      [11, 18],
      [8, 20],
      [8.5, 17.2],
      [5.5, 15],
      [4, 11],
      [4.8, 7],
      [7, 4],
      [13, 2],
    ],
  ],
  X = [
    [
      [6, 6],
      [7.7, 7.7],
      [9.4, 9.4],
      [11.1, 11.1],
      [12.9, 12.9],
      [14.6, 14.6],
      [16.3, 16.3],
      [18, 18],
    ],
    [
      [18, 6],
      [16.3, 7.7],
      [14.6, 9.4],
      [12.9, 11.1],
      [11.1, 12.9],
      [9.4, 14.6],
      [7.7, 16.3],
      [6, 18],
    ],
  ];
export function FeedbackControl({
  analysisId,
  target,
  failure = false,
}: {
  analysisId: string;
  target: FeedbackTarget;
  failure?: boolean;
}) {
  const [phase, setPhase] = useState<Phase>("idle"),
    [rating, setRating] = useState<Rating>(
      failure ? "not_helpful" : (target.response?.rating ?? null),
    ),
    [comment, setComment] = useState(target.response?.comment ?? ""),
    [confirmed, setConfirmed] = useState<FeedbackResponse | null>(
      target.response,
    ),
    [mounted, setMounted] = useState(false),
    [error, setError] = useState(false),
    [height, setHeight] = useState(36),
    [placement, setPlacement] = useState<{ right: number; top: number; bottom: number; openUp: boolean } | null>(null);
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
  const tooltip = useId(),
    draftKey = `cv-feedback-draft:${analysisId}:${target.target_id}`,
    open = phase === "open",
    sending = ["collapsing", "launching", "delivered", "resetting"].includes(
      phase,
    ),
    normalized = comment.trim().replace(/\s+/g, " "),
    valid = failure || (normalized.length >= 12 && normalized.length <= 180);
  const draw = useCallback(
    (value: number) =>
      path.current?.setAttribute(
        "d",
        B.map((line, li) =>
          line
            .map((point, i) => {
              const t = X[li][i],
                x = point[0] + (t[0] - point[0]) * value,
                y = point[1] + (t[1] - point[1]) * value;
              return `${i ? "L" : "M"}${x.toFixed(2)} ${y.toFixed(2)}`;
            })
            .join(""),
        ).join(""),
      ),
    [],
  );
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
  const position = useCallback(() => {
    const rect = anchor.current?.getBoundingClientRect();
    if (!rect) return;
    setPlacement({
      right: window.innerWidth - rect.right - 10,
      top: rect.top - 10,
      bottom: window.innerHeight - rect.bottom - 10,
      openUp: rect.bottom + 138 > window.innerHeight,
    });
  }, []);
  const close = useCallback(() => {
    if (sending) return;
    setPhase("idle");
    morph(0);
    requestAnimationFrame(() => trigger.current?.focus());
  }, [morph, sending]);
  useLayoutEffect(() => {
    const resizeObserver = new ResizeObserver(position);
    resizeObserver.observe(document.body);
    window.addEventListener("resize", position);
    window.addEventListener("scroll", position, true);
    return () => {
      resizeObserver.disconnect();
      window.removeEventListener("resize", position);
      window.removeEventListener("scroll", position, true);
    };
  }, [position]);
  useEffect(() => {
    setMounted(true);
  }, []);
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
      position();
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
    const body = failure
      ? {
          rating: "not_helpful",
          reason: "operation_failed",
          comment: normalized || null,
        }
      : {
          rating,
          reason: rating === "not_helpful" ? "other" : null,
          comment: normalized || null,
        };
    try {
      const response = await fetch(
        `/api/analyses/${encodeURIComponent(analysisId)}/feedback/${encodeURIComponent(target.target_id)}`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
      );
      if (!response.ok) throw new Error();
      setConfirmed(await response.json());
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
    classes = ["feedback-cloud", phase, placement ? "positioned" : "", placement?.openUp ? "open-up" : "", confirmed ? "has-response" : ""]
      .filter(Boolean)
      .join(" ");
  return (
    <>
    <div
      ref={anchor}
      className="feedback-anchor"
      data-feedback-target={target.target_id}
    />
    {mounted ? createPortal(<>
      <div
        ref={cloud}
        className={classes}
        style={{
          "--comment-h": `${height}px`,
          "--cloud-right": `${placement?.right ?? 0}px`,
          "--cloud-top": `${placement?.top ?? 0}px`,
          "--cloud-bottom": `${placement?.bottom ?? 0}px`,
        } as React.CSSProperties}
      >
        <button
          ref={trigger}
          className="feedback-trigger"
          type="button"
          onClick={toggle}
          aria-label={
            open ? "Zamknij feedback" : failure ? "Zgłoś problem" : "Oceń wynik"
          }
          aria-expanded={open}
          aria-describedby={!open ? tooltip : undefined}
        >
          <svg
            className="feedback-morph-icon"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <path
              ref={path}
              d="M13 2L17 2.8L20 5.5L22 9L21.5 13L19 16.5L15 18L11 18M11 18L8 20L8.5 17.2L5.5 15L4 11L4.8 7L7 4L13 2"
            />
          </svg>
        </button>
        <section
          className="feedback-panel"
          aria-label="Feedback do wyniku"
          aria-hidden={!open}
        >
          {!failure ? (
            <div className="feedback-actions">
              <button
                className={`feedback-vote ${rating === "helpful" ? "selected" : ""}`}
                type="button"
                onClick={() => select("helpful")}
                aria-label="Pomocny"
                aria-pressed={rating === "helpful"}
              >
                <Thumb up />
              </button>
              <button
                className={`feedback-vote ${rating === "not_helpful" ? "selected" : ""}`}
                type="button"
                onClick={() => select("not_helpful")}
                aria-label="Do poprawy"
                aria-pressed={rating === "not_helpful"}
              >
                <Thumb />
              </button>
            </div>
          ) : (
            <div className="feedback-actions feedback-failure-label">
              Zgłoś problem
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
                rating === "not_helpful" ? "Co poprawić?" : "Napisz…"
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
              aria-label="Komentarz"
            />
            <span
              className="feedback-counter"
              style={{ opacity: counterOpacity }}
            >
              {remaining}
            </span>
            <button
              className="feedback-send"
              type="button"
              disabled={!valid || sending}
              onClick={() => void send()}
              aria-label="Wyślij"
              aria-keyshortcuts="Control+Enter Meta+Enter"
            >
              <Plane />
            </button>
          </div>
          {error ? (
            <span className="feedback-error">Nie udało się zapisać</span>
          ) : null}
        </section>
        <div className="feedback-send-stage" role="status">
          <Plane className="feedback-stage-plane" />
          <div className="feedback-stage-copy">
            <span>Wysłano!</span>
          </div>
        </div>
      </div>
      <span id={tooltip} className="feedback-tooltip" role="tooltip">
        {failure ? "Zgłoś problem" : "Przekaż opinię"}
      </span>
    </>, document.body) : null}
    </>
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
