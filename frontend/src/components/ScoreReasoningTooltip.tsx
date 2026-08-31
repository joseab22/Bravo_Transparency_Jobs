import { useState } from "react";

import { ConfidenceGauge } from "@/components/ConfidenceGauge";
import { confidenceLabel, fallbackScoreReasoning, signedPoints } from "@/lib/jobFormatting";
import type { JobListItem } from "@/types/jobs";

export function ScoreReasoningTooltip({ job }: { job: JobListItem }) {
  const [open, setOpen] = useState(false);
  const confidence = job.active_hiring_confidence;
  const reasoning = job.active_hiring_reasoning ?? fallbackScoreReasoning(job);

  if (confidence == null || !reasoning) {
    return (
      <div className="flex shrink-0 items-center gap-2 text-left">
        <ConfidenceGauge confidence={null} size={44} />
        <p className="text-sm text-ink-muted">Not scored</p>
      </div>
    );
  }

  const visibilityClasses = open
    ? "pointer-events-auto visible translate-y-0 opacity-100"
    : "pointer-events-none invisible translate-y-1 opacity-0 group-hover:pointer-events-auto group-hover:visible group-hover:translate-y-0 group-hover:opacity-100 group-focus-within:pointer-events-auto group-focus-within:visible group-focus-within:translate-y-0 group-focus-within:opacity-100";

  return (
    <div
      className="group relative z-20 shrink-0 text-left hover:z-50 focus-within:z-50"
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget as Node | null)) {
          setOpen(false);
        }
      }}
    >
      <button
        type="button"
        aria-label={`Active Hiring Confidence ${Math.round(confidence)}. Show score explanation.`}
        aria-describedby={`score-reasoning-${job.id}`}
        aria-expanded={open}
        onClick={() => setOpen((current) => !current)}
        className="flex items-center gap-2 rounded-lg px-2 py-1 text-left outline-none ring-accent transition hover:bg-surface-2 focus-visible:ring-2"
      >
        <ConfidenceGauge confidence={confidence} size={44} />
        <span className="text-sm text-ink-muted">
          {confidenceLabel(confidence)}
          <span className="block font-medium text-accent">Why? →</span>
        </span>
      </button>

      <div
        id={`score-reasoning-${job.id}`}
        role="tooltip"
        className={`absolute right-0 top-full z-50 mt-2 max-h-[70vh] w-[min(26rem,calc(100vw-2rem))] overflow-y-auto rounded-xl border border-line bg-page p-4 text-left shadow-2xl transition ${visibilityClasses}`}
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-sm font-semibold text-accent">Why this score</p>
            <p className="mt-1 text-sm leading-5 text-ink-secondary">{reasoning.summary}</p>
          </div>
          <span className="rounded-full border border-line px-2 py-1 text-xs font-semibold text-ink-secondary">
            {reasoning.score.toFixed(1)}/100
          </span>
        </div>

        <p className="mt-3 rounded-lg bg-surface px-3 py-2 text-xs leading-5 text-ink-muted">
          <span className="font-semibold text-ink-secondary">How the score is calculated: </span>
          {reasoning.formula}
        </p>

        <div className="mt-4 space-y-4">
          {reasoning.components.map((component) => (
            <div key={component.key}>
              <div className="flex items-center justify-between gap-3 text-sm">
                <span className="font-medium text-ink-secondary">{component.label}</span>
                <span
                  className={
                    component.tone === "positive"
                      ? "font-semibold text-positive"
                      : component.tone === "negative"
                        ? "font-semibold text-negative"
                        : "font-semibold text-warning"
                  }
                >
                  {signedPoints(component.points)}
                  {component.maximum != null ? ` / ${component.maximum.toFixed(0)}` : ""}
                </span>
              </div>
              <p className="mt-1 text-xs leading-5 text-ink-muted">{component.detail}</p>
            </div>
          ))}
        </div>

        {reasoning.signals.length > 0 && (
          <div className="mt-4 border-t border-line-subtle pt-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-ink-muted">
              What JobLens observed
            </p>
            <ul className="mt-2 space-y-1 text-xs leading-5 text-ink-secondary">
              {reasoning.signals.slice(0, 6).map((signal) => (
                <li key={signal}>• {signal}</li>
              ))}
            </ul>
          </div>
        )}

        {reasoning.limitations.length > 0 && (
          <div className="mt-4 border-t border-line-subtle pt-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-ink-faint">
              What JobLens could not verify
            </p>
            <ul className="mt-2 space-y-1 text-xs leading-5 text-ink-faint">
              {reasoning.limitations.map((limitation) => (
                <li key={limitation}>• {limitation}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
