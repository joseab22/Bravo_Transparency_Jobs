import type { ActiveHiringReasoning, JobDetail, JobEvent, JobListItem, RepostEvent } from "@/types/jobs";

const MILLISECONDS_PER_DAY = 86_400_000;

export function parseApiDate(value?: string | null): Date | null {
  if (!value) return null;

  const normalized = /(?:Z|[+-]\d{2}:\d{2})$/.test(value) ? value : `${value}Z`;
  const parsed = new Date(normalized);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

export function utcDayNumber(value?: string | null): number | null {
  const parsed = parseApiDate(value);
  if (!parsed) return null;

  return Math.floor(
    Date.UTC(parsed.getUTCFullYear(), parsed.getUTCMonth(), parsed.getUTCDate()) /
      MILLISECONDS_PER_DAY,
  );
}

export function daysAgo(value?: string | null): number | null {
  const day = utcDayNumber(value);
  if (day == null) return null;

  const now = new Date();
  const today = Math.floor(
    Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate()) /
      MILLISECONDS_PER_DAY,
  );

  return Math.max(today - day, 0);
}

export function daysBetween(start?: string | null, end?: string | null): number | null {
  const startDay = utcDayNumber(start);
  const endDay = utcDayNumber(end);
  if (startDay == null || endDay == null) return null;

  return Math.max(endDay - startDay, 0);
}

export function dayLabel(value: number): string {
  return `${value} day${value === 1 ? "" : "s"}`;
}

export function ageSummary(job: JobListItem): string {
  const postingAge = daysAgo(job.date_posted);
  const firstSeenAge = daysAgo(job.date_first_seen);
  const trackedDays = daysBetween(job.date_first_seen, job.date_last_seen);

  const postingText =
    postingAge == null
      ? firstSeenAge === 0
        ? "first observed today"
        : firstSeenAge == null
          ? "posting date unavailable"
          : `first observed ${dayLabel(firstSeenAge)} ago`
      : postingAge === 0
        ? "posted today"
        : `posted ${dayLabel(postingAge)} ago`;

  const trackingText =
    trackedDays == null
      ? null
      : trackedDays === 0
        ? "tracked today"
        : `tracked for ${dayLabel(trackedDays)}`;

  return trackingText ? `${postingText} · ${trackingText}` : postingText;
}

export function postingDateLabel(job: JobListItem): string | null {
  const parsed = parseApiDate(job.date_posted) ?? parseApiDate(job.date_first_seen);
  if (!parsed) return null;

  // timeZone must be pinned, not left to the runtime default: this renders
  // both server-side (SSR on /jobs/[id], in the container's UTC) and
  // client-side (hydration, in the visitor's local zone). Near a UTC day
  // boundary those disagree on the calendar date without this, which is a
  // hydration mismatch, not just a display quirk.
  return parsed.toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric", timeZone: "UTC" });
}

// Exact text of the "parallel" classification's signal (must match
// scoring.py's identical literal and this file's own copy below).
// ScoreReasoningTooltip matches against this to render that one signal as
// a clickable "show these jobs" control instead of plain bullet text --
// job.listing_classification === "parallel" is the authoritative check;
// this string match only decides *where* in the rendered signals list that
// control appears. If the wording ever drifts out of sync, the failure
// mode is graceful (that bullet just renders as plain text again), not a
// broken or misleading UI.
export const RELATED_OPENINGS_SIGNAL = "Related openings appear to be active at the same time.";

export function confidenceLabel(value?: number | null): string {
  if (value == null) return "Not scored";
  if (value >= 70) return "Higher confidence";
  if (value >= 45) return "Mixed signals";
  return "Lower confidence";
}

export type ConfidenceBand = "high" | "medium" | "low" | "unknown";

// Single source of truth for the 70/45 thresholds -- previously duplicated
// (and kept manually in sync) across JobListRow, ScoreReasoningTooltip, and
// this file's own confidenceLabel/summary logic.
export function confidenceBand(value?: number | null): ConfidenceBand {
  if (value == null) return "unknown";
  if (value >= 70) return "high";
  if (value >= 45) return "medium";
  return "low";
}

export function signedPoints(value: number): string {
  return `${value > 0 ? "+" : ""}${value.toFixed(1)}`;
}

export function clamp(value: number, minimum: number, maximum: number): number {
  return Math.min(Math.max(value, minimum), maximum);
}

export function joinItems(items: string[]): string {
  if (items.length === 0) return "";
  if (items.length === 1) return items[0];
  if (items.length === 2) return `${items[0]} and ${items[1]}`;
  return `${items.slice(0, -1).join(", ")}, and ${items[items.length - 1]}`;
}

export function safeExternalUrl(value?: string | null): string | null {
  if (!value) return null;

  try {
    const parsed = new URL(value);

    if (parsed.protocol !== "https:" && parsed.protocol !== "http:") {
      return null;
    }

    if (parsed.username || parsed.password) {
      return null;
    }

    return parsed.toString();
  } catch {
    return null;
  }
}

export function sourceLinks(job: JobListItem) {
  const activeCanonicalSources = job.canonical_sources.filter((source) => source.is_active);
  const sources = activeCanonicalSources.length
    ? activeCanonicalSources
    : [
        {
          sighting_key: `legacy-${job.id}-${job.source}`,
          source: job.source,
          publisher_name: job.publisher_name || job.source,
          source_url: job.source_url,
          collection_provider: job.collection_provider,
          external_id: null,
          is_direct: false,
          first_seen: job.date_first_seen,
          last_seen: job.date_last_seen,
          is_active: job.is_active,
          listing_ids: [job.id],
        },
      ];

  const totals = sources.reduce<Record<string, number>>((counts, source) => {
    counts[source.publisher_name] = (counts[source.publisher_name] || 0) + 1;
    return counts;
  }, {});

  const seen: Record<string, number> = {};

  return sources.map((source) => {
    seen[source.publisher_name] = (seen[source.publisher_name] || 0) + 1;

    const label =
      totals[source.publisher_name] > 1
        ? `${source.publisher_name} ${seen[source.publisher_name]}`
        : source.publisher_name;

    return { source, label };
  });
}

export function distinctBoardCount(job: JobListItem): number {
  return new Set(sourceLinks(job).map(({ source }) => source.publisher_name)).size;
}

export function formatSalary(job: JobListItem): string | null {
  if (!job.salary_listed || (job.salary_min == null && job.salary_max == null)) {
    return null;
  }

  const formatter = new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: job.salary_currency || "USD",
    maximumFractionDigits: 0,
  });

  if (job.salary_min != null && job.salary_max != null) {
    return `${formatter.format(job.salary_min)}–${formatter.format(job.salary_max)}`;
  }

  return formatter.format(job.salary_min ?? job.salary_max ?? 0);
}

// KEEP IN SYNC with ScoringService.active_hiring_reasoning() and
// ScoringService._active_hiring_components() in
// backend/app/services/scoring.py. This function only runs if the API
// response for a scored job is missing active_hiring_reasoning (normally
// unreachable: the API always computes it whenever active_hiring_confidence
// is set), so it exists as a defensive fallback, not the primary path.
// There is no automated test pinning these two implementations together
// (this frontend project has no test runner configured) -- any change to
// the backend's weights (60/30/10 point caps), thresholds (ghost <0.25/
// <0.50, activity >=75/>=45, evidence >=0.70/>=0.40), or adjustment values
// (+5 parallel, -8 repost, -25 inactive) must be mirrored here by hand, or
// this fallback will silently disagree with the real score's explanation.
export function fallbackScoreReasoning(job: JobListItem): ActiveHiringReasoning | null {
  const score = job.active_hiring_confidence;
  if (score == null) return null;

  const ghost = clamp(job.ghost_job_probability ?? 0.5, 0, 1);
  const activity = clamp(job.activity_score ?? 0, 0, 100);
  const evidence = clamp(job.ghost_confidence ?? 0, 0, 1);
  const classification = (job.listing_classification || "original").toLowerCase();
  const sourceCount = job.canonical_sources?.length ?? 0;
  const daysActive = Math.max(job.days_active ?? 0, 0);

  const postingHealth = (1 - ghost) * 60;
  const activityPoints = activity * 0.3;
  const evidencePoints = evidence * 10;
  const listingAdjustment =
    classification === "parallel" ? 5 : classification === "repost" ? -8 : 0;
  const availabilityAdjustment = job.is_active ? 0 : -25;

  const healthInterpretation =
    ghost < 0.25
      ? "JobLens found few warning signs associated with stale or repeatedly recycled listings."
      : ghost < 0.5
        ? "JobLens found some warning signs, but the posting is not in the highest-risk range."
        : "JobLens found several warning signs associated with stale or repeatedly recycled listings.";

  const activityInterpretation =
    activity >= 75
      ? "This is a strong signal that the employer may be recruiting now."
      : activity >= 45
        ? "There is some current activity, but it is not as strong or consistent as higher-scoring postings."
        : "Current activity signals are limited, which makes immediate hiring less certain.";

  const evidenceInterpretation =
    evidence >= 0.7
      ? "The score is supported by several observations or supporting data fields."
      : evidence >= 0.4
        ? "The score has some supporting evidence, but important information is still missing."
        : "The score is based on limited supporting evidence, so it should be treated with more caution.";

  const companyRating = job.company?.glassdoor_rating ?? null;
  const presentEvidence: string[] = [];
  if (job.salary_listed) presentEvidence.push("salary disclosure");
  if (job.applicant_count != null) presentEvidence.push("applicant count");
  if (companyRating != null) presentEvidence.push("company rating");

  const components: ActiveHiringReasoning["components"] = [
    {
      key: "posting_health",
      label: "Posting reliability",
      points: Number(postingHealth.toFixed(1)),
      maximum: 60,
      tone: ghost < 0.35 ? "positive" : ghost >= 0.6 ? "negative" : "neutral",
      detail: `Estimated stale or recycled listing risk is ${Math.round(ghost * 100)}%. ${healthInterpretation} ${
        job.repost_count
          ? `This listing has ${job.repost_count} repost${job.repost_count !== 1 ? "s" : ""} on record.`
          : "No repost history is recorded for this listing."
      }`,
    },
    {
      key: "activity",
      label: "Recent hiring activity",
      points: Number(activityPoints.toFixed(1)),
      maximum: 30,
      tone: activity >= 65 ? "positive" : activity < 35 ? "negative" : "neutral",
      detail: `Activity is ${Math.round(activity)}/100. ${activityInterpretation} First observed ${daysActive} day${daysActive !== 1 ? "s" : ""} ago${
        sourceCount > 1 ? `, found across ${sourceCount} sources.` : "."
      }`,
    },
    {
      key: "evidence",
      label: "Strength of evidence",
      points: Number(evidencePoints.toFixed(1)),
      maximum: 10,
      tone: evidence >= 0.65 ? "positive" : evidence < 0.35 ? "negative" : "neutral",
      detail: `Evidence confidence is ${Math.round(evidence * 100)}%. ${evidenceInterpretation} ${
        presentEvidence.length > 0
          ? `Supported by ${joinItems(presentEvidence)}.`
          : "No supporting data points (salary, applicant count, or company rating) are available."
      }`,
    },
  ];

  if (listingAdjustment !== 0) {
    components.push({
      key: "listing_pattern",
      label: "Listing history",
      points: listingAdjustment,
      maximum: null,
      tone: listingAdjustment > 0 ? "positive" : "negative",
      detail:
        listingAdjustment > 0
          ? "JobLens found multiple active listings that appear to represent separate openings for the same role. This adds 5 points because simultaneous openings can indicate team, location, or volume hiring."
          : "The role appeared again after an earlier listing. A repost can mean continued recruiting, but it can also mean the opening was recycled or remained unfilled, so 8 points are removed.",
    });
  }

  if (availabilityAdjustment !== 0) {
    components.push({
      key: "availability",
      label: "Current availability",
      points: availabilityAdjustment,
      maximum: null,
      tone: "negative",
      detail: "JobLens currently marks this listing inactive, so 25 points are removed.",
    });
  }

  const signals: string[] = [];
  if (!job.is_active) {
    signals.push("The listing is currently marked inactive in JobLens.");
  } else if (daysActive <= 14) {
    signals.push(
      `The role was posted or first observed ${daysActive} day${daysActive === 1 ? "" : "s"} ago, which is recent.`,
    );
  } else if (daysActive >= 90) {
    signals.push(
      `The listing has been visible for ${daysActive} days, which can increase uncertainty if other activity signals are weak.`,
    );
  } else {
    signals.push(`The listing has been tracked for ${daysActive} days and is still marked active.`);
  }

  if (sourceCount > 1) {
    signals.push(
      `The same role was found in ${sourceCount} source listings, providing cross-source support.`,
    );
  } else if (sourceCount === 1) {
    signals.push("The role has been found through one source listing so far.");
  }

  if (job.repost_count > 0) {
    signals.push(
      `JobLens detected ${job.repost_count} prior occurrence${job.repost_count === 1 ? "" : "s"} of this role.`,
    );
  } else if (classification === "parallel") {
    signals.push(RELATED_OPENINGS_SIGNAL);
  } else {
    signals.push("No repost history is currently recorded.");
  }

  if (job.salary_listed) signals.push("The employer disclosed compensation in the listing.");
  if (job.applicant_count != null) {
    signals.push(`Reported applicant count: ${job.applicant_count.toLocaleString()}.`);
  }

  const limitations: string[] = [];
  if (job.applicant_count == null) {
    limitations.push("Applicant count was not available, so it could not support the estimate.");
  }
  if (!job.salary_listed) {
    limitations.push("Compensation was not listed, reducing the available transparency evidence.");
  }
  if (sourceCount <= 1) {
    limitations.push("Only one source listing has been observed, so cross-source support is limited.");
  }
  limitations.push(
    "The score estimates hiring activity from observable posting behavior. It cannot confirm that the employer is interviewing or will fill the role.",
  );

  const positiveFactors: string[] = [];
  if (ghost < 0.25) positiveFactors.push("low estimated stale-listing risk");
  if (activity >= 75) positiveFactors.push("strong recent activity");
  if (evidence >= 0.7) positiveFactors.push("strong supporting evidence");
  if (classification === "parallel") positiveFactors.push("multiple related openings");
  if (sourceCount > 1) positiveFactors.push("cross-source support");

  const concernFactors: string[] = [];
  if (!job.is_active) concernFactors.push("inactive status");
  if (classification === "repost") concernFactors.push("repost history");
  if (ghost >= 0.35) concernFactors.push("elevated stale-listing risk");
  if (activity < 60) concernFactors.push("weaker recent activity");
  if (evidence < 0.5) concernFactors.push("limited supporting evidence");
  if (daysActive >= 90) concernFactors.push("a long-running listing");

  let summary: string;
  if (score >= 85) {
    const reason = joinItems(positiveFactors.slice(0, 3)) || "several positive hiring signals";
    summary = `Strong signs of active hiring. Positive signals include ${reason}.`;
  } else if (score >= 70) {
    const reason =
      joinItems(positiveFactors.slice(0, 2)) || "mostly positive posting and activity signals";
    summary = `Good signs of active hiring. The strongest signals are ${reason}, although some information may still be limited.`;
  } else if (score >= 45) {
    const reason = joinItems(concernFactors.slice(0, 3)) || "incomplete or conflicting evidence";
    summary = `Some positive signals, but meaningful uncertainty. ${reason.charAt(0).toUpperCase()}${reason.slice(1)} reduce confidence in immediate hiring.`;
  } else {
    const reason =
      joinItems(concernFactors.slice(0, 3)) || "limited evidence of current hiring activity";
    summary = `Limited signs of active hiring. The main concerns are ${reason}. Verify the role on the employer's careers page before relying on the listing.`;
  }

  return {
    score,
    label: confidenceLabel(score),
    summary,
    formula:
      "Posting reliability contributes up to 60 points, recent activity up to 30, and evidence strength up to 10. Listing history and inactive status can add or subtract points.",
    components,
    signals,
    limitations,
  };
}

export interface TimelineEntry {
  key: string;
  date: string;
  label: string;
  detail?: string;
}

const currencyFormatter = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});

function isSalaryPair(value: unknown): value is [number | null, number | null] {
  return Array.isArray(value) && value.length === 2;
}

function formatSalaryPair(pair: [number | null, number | null]): string | null {
  const [min, max] = pair;
  if (min == null && max == null) return null;
  if (min != null && max != null) return `${currencyFormatter.format(min)}–${currencyFormatter.format(max)}`;
  return currencyFormatter.format((min ?? max) as number);
}

function describeEvent(event: JobEvent): { label: string; detail?: string } {
  const payload = event.payload ?? {};

  switch (event.event_type) {
    case "created":
      return { label: "First tracked by JobLens" };

    case "title_changed": {
      const oldTitle = payload.old;
      const newTitle = payload.new;
      return {
        label: "Title changed",
        detail:
          typeof oldTitle === "string" && typeof newTitle === "string"
            ? `"${oldTitle}" became "${newTitle}"`
            : (event.description ?? undefined),
      };
    }

    case "description_changed":
      return { label: "Description updated", detail: event.description ?? undefined };

    case "salary_changed": {
      const oldPair = isSalaryPair(payload.old) ? formatSalaryPair(payload.old) : null;
      const newPair = isSalaryPair(payload.new) ? formatSalaryPair(payload.new) : null;
      return {
        label: "Compensation changed",
        detail: oldPair && newPair ? `${oldPair} became ${newPair}` : (newPair ?? undefined),
      };
    }

    case "applicant_spike": {
      const oldCount = payload.old;
      const newCount = payload.new;
      return {
        label: "Applicant count jumped",
        detail:
          typeof oldCount === "number" && typeof newCount === "number"
            ? `${oldCount.toLocaleString()} became ${newCount.toLocaleString()} reported applicants`
            : undefined,
      };
    }

    case "location_changed":
      return { label: "Location or work type changed" };

    case "expired":
      return { label: "Marked inactive", detail: event.description ?? undefined };

    case "reactivated":
      return {
        label: "Reactivated",
        detail: event.description ?? "This listing became active again after being marked inactive.",
      };

    case "source_added": {
      const publisher = typeof payload.publisher_name === "string" ? payload.publisher_name : null;
      return { label: publisher ? `Also found on ${publisher}` : "Found on another source" };
    }

    case "ghost_flagged":
      return { label: "Flagged as a likely ghost job", detail: event.description ?? undefined };

    default:
      return { label: event.event_type.replace(/_/g, " "), detail: event.description ?? undefined };
  }
}

// days_since_previous is a gap computed against a *different, earlier*
// listing for the same job (see repost_detector.py), not against anything
// else on this timeline -- this listing's own date_seen minus that gap is
// the earlier listing's last-confirmed-active date. Showing that date (not
// just "N days before") is what makes the entry legible on its own instead
// of requiring the reader to do the subtraction themselves.
function repostDetail(repost: RepostEvent): string | undefined {
  if (repost.days_since_previous == null) return undefined;

  const seen = parseApiDate(repost.date_seen);
  const days = repost.days_since_previous;
  const dayLabel = `${days} day${days === 1 ? "" : "s"}`;

  if (!seen) return `A separate listing for this same job was last confirmed active ${dayLabel} before this one appeared`;

  const previousDate = new Date(seen.getTime() - days * MILLISECONDS_PER_DAY);
  const previousDateLabel = previousDate.toLocaleDateString("en-US", {
    year: "numeric", month: "short", day: "numeric", timeZone: "UTC",
  });

  return `A separate listing for this same job was last confirmed active on ${previousDateLabel} (${dayLabel} before this one appeared)`;
}

// Merges JobEvent rows (title/salary/location changes, activation state) and
// RepostEvent rows (a separate table specifically tracking repost
// occurrences) into one chronological history, newest first. Both sources
// are already returned by the API on JobPostingDetail; this only formats
// them into a readable narrative.
export function buildTimeline(job: JobDetail): TimelineEntry[] {
  const entries: TimelineEntry[] = [];

  for (const event of job.events ?? []) {
    if (!parseApiDate(event.timestamp)) continue;
    const { label, detail } = describeEvent(event);
    entries.push({ key: `event-${event.id}`, date: event.timestamp, label, detail });
  }

  for (const repost of job.repost_events ?? []) {
    if (!parseApiDate(repost.date_seen)) continue;
    entries.push({
      key: `repost-${repost.occurrence_number}-${repost.date_seen}`,
      date: repost.date_seen,
      label: `Reposted (occurrence #${repost.occurrence_number})`,
      // This listing's own date_first_seen doubles as its "date seen" for
      // repost purposes, so this entry can land on the same calendar date as
      // a "First tracked by JobLens" entry just above it. The gap below is
      // measured against a *different, earlier* listing for the same job,
      // not against anything else on this timeline -- word it that way, or
      // it reads as a contradiction ("just discovered" next to "day-old
      // history") instead of two true facts about the same listing.
      detail: repostDetail(repost),
    });
  }

  return entries.sort((a, b) => (a.date < b.date ? 1 : a.date > b.date ? -1 : 0));
}
