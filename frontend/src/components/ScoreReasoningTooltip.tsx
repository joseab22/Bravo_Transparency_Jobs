import { useState } from "react";

import { confidenceLabel, fallbackScoreReasoning, signedPoints } from "@/lib/jobFormatting";
import type { JobListItem } from "@/types/jobs";

export function ScoreReasoningTooltip({ job }: { job: JobListItem }) {
  const [open, setOpen] = useState(false);
  const confidence = job.active_hiring_confidence;
  const reasoning = job.active_hiring_reasoning ?? fallbackScoreReasoning(job);
  const scoreClass =
    confidence == null
      ? "unknown"
      : confidence >= 70
        ? "high"
        : confidence >= 45
          ? "medium"
          : "low";

  if (confidence == null || !reasoning) {
    return (
      <div className="shrink-0 text-left sm:text-right">
        <p className={`confidence ${scoreClass}`}>N/A</p>
        <p className="text-sm text-slate-400">Not scored</p>
      </div>
    );
  }

  const visibilityClasses = open
    ? "pointer-events-auto visible translate-y-0 opacity-100"
    : "pointer-events-none invisible translate-y-1 opacity-0 group-hover:pointer-events-auto group-hover:visible group-hover:translate-y-0 group-hover:opacity-100 group-focus-within:pointer-events-auto group-focus-within:visible group-focus-within:translate-y-0 group-focus-within:opacity-100";

  return (
    <div
      className="group relative z-20 shrink-0 text-left hover:z-50 focus-within:z-50 sm:text-right"
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
        className="rounded-lg px-2 py-1 text-left outline-none ring-cyan-300 transition hover:bg-slate-800 focus-visible:ring-2 sm:text-right"
      >
        <span className={`confidence ${scoreClass}`}>{Math.round(confidence)}</span>
        <span className="block text-sm text-slate-400">
          {confidenceLabel(confidence)} · Why?
        </span>
      </button>

      <div
        id={`score-reasoning-${job.id}`}
        role="tooltip"
        className={`absolute right-0 top-full z-50 mt-2 max-h-[70vh] w-[min(26rem,calc(100vw-2rem))] overflow-y-auto rounded-xl border border-slate-700 bg-slate-950 p-4 text-left shadow-2xl transition ${visibilityClasses}`}
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-sm font-semibold text-cyan-200">Why this score</p>
            <p className="mt-1 text-sm leading-5 text-slate-300">{reasoning.summary}</p>
          </div>
          <span className="rounded-full border border-slate-700 px-2 py-1 text-xs font-semibold text-slate-200">
            {reasoning.score.toFixed(1)}/100
          </span>
        </div>

        <p className="mt-3 rounded-lg bg-slate-900 px-3 py-2 text-xs leading-5 text-slate-400">
          <span className="font-semibold text-slate-300">How the score is calculated: </span>
          {reasoning.formula}
        </p>

        <div className="mt-4 space-y-4">
          {reasoning.components.map((component) => (
            <div key={component.key}>
              <div className="flex items-center justify-between gap-3 text-sm">
                <span className="font-medium text-slate-200">{component.label}</span>
                <span
                  className={
                    component.tone === "positive"
                      ? "font-semibold text-emerald-300"
                      : component.tone === "negative"
                        ? "font-semibold text-rose-300"
                        : "font-semibold text-amber-200"
                  }
                >
                  {signedPoints(component.points)}
                  {component.maximum != null ? ` / ${component.maximum.toFixed(0)}` : ""}
                </span>
              </div>
              <p className="mt-1 text-xs leading-5 text-slate-400">{component.detail}</p>
            </div>
          ))}
        </div>

        {reasoning.signals.length > 0 && (
          <div className="mt-4 border-t border-slate-800 pt-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
              What JobLens observed
            </p>
            <ul className="mt-2 space-y-1 text-xs leading-5 text-slate-300">
              {reasoning.signals.slice(0, 6).map((signal) => (
                <li key={signal}>• {signal}</li>
              ))}
            </ul>
          </div>
        )}

        {reasoning.limitations.length > 0 && (
          <div className="mt-4 border-t border-slate-800 pt-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              What JobLens could not verify
            </p>
            <ul className="mt-2 space-y-1 text-xs leading-5 text-slate-500">
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
