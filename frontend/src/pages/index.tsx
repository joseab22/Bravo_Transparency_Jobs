import Head from "next/head";
import { useEffect, useState } from "react";

import { jobsApi } from "@/lib/api";
import type { ActiveHiringReasoning, JobListItem } from "@/types/jobs";

const PAGE_SIZE = 50;
const DEFAULT_MAX_AGE_DAYS = 30;
const MILLISECONDS_PER_DAY = 86_400_000;

function parseApiDate(value?: string | null): Date | null {
  if (!value) return null;

  const normalized = /(?:Z|[+-]\d{2}:\d{2})$/.test(value) ? value : `${value}Z`;
  const parsed = new Date(normalized);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

function utcDayNumber(value?: string | null): number | null {
  const parsed = parseApiDate(value);
  if (!parsed) return null;

  return Math.floor(
    Date.UTC(parsed.getUTCFullYear(), parsed.getUTCMonth(), parsed.getUTCDate()) /
      MILLISECONDS_PER_DAY,
  );
}

function daysAgo(value?: string | null): number | null {
  const day = utcDayNumber(value);
  if (day == null) return null;

  const now = new Date();
  const today = Math.floor(
    Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate()) /
      MILLISECONDS_PER_DAY,
  );

  return Math.max(today - day, 0);
}

function daysBetween(start?: string | null, end?: string | null): number | null {
  const startDay = utcDayNumber(start);
  const endDay = utcDayNumber(end);
  if (startDay == null || endDay == null) return null;

  return Math.max(endDay - startDay, 0);
}

function dayLabel(value: number): string {
  return `${value} day${value === 1 ? "" : "s"}`;
}

function ageSummary(job: JobListItem): string {
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

function confidenceLabel(value?: number | null): string {
  if (value == null) return "Not scored";
  if (value >= 70) return "Higher confidence";
  if (value >= 45) return "Mixed signals";
  return "Lower confidence";
}

function signedPoints(value: number): string {
  return `${value > 0 ? "+" : ""}${value.toFixed(1)}`;
}

function clamp(value: number, minimum: number, maximum: number): number {
  return Math.min(Math.max(value, minimum), maximum);
}

function joinItems(items: string[]): string {
  if (items.length === 0) return "";
  if (items.length === 1) return items[0];
  if (items.length === 2) return `${items[0]} and ${items[1]}`;
  return `${items.slice(0, -1).join(", ")}, and ${items[items.length - 1]}`;
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
function fallbackScoreReasoning(job: JobListItem): ActiveHiringReasoning | null {
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

  const components: ActiveHiringReasoning["components"] = [
    {
      key: "posting_health",
      label: "Posting reliability",
      points: Number(postingHealth.toFixed(1)),
      maximum: 60,
      tone: ghost < 0.35 ? "positive" : ghost >= 0.6 ? "negative" : "neutral",
      detail: `Estimated stale or recycled listing risk is ${Math.round(ghost * 100)}%. ${healthInterpretation} The estimate considers posting age, repost history, salary disclosure, applicant count and company rating when available, and similar listings from the same employer.`,
    },
    {
      key: "activity",
      label: "Recent hiring activity",
      points: Number(activityPoints.toFixed(1)),
      maximum: 30,
      tone: activity >= 65 ? "positive" : activity < 35 ? "negative" : "neutral",
      detail: `Activity is ${Math.round(activity)}/100. JobLens considers how recently the role appeared, whether related listings are active, and whether the posting has been observed more than once. ${activityInterpretation}`,
    },
    {
      key: "evidence",
      label: "Strength of evidence",
      points: Number(evidencePoints.toFixed(1)),
      maximum: 10,
      tone: evidence >= 0.65 ? "positive" : evidence < 0.35 ? "negative" : "neutral",
      detail: `Evidence confidence is ${Math.round(evidence * 100)}%. ${evidenceInterpretation} Evidence can include repeated observations, compensation data, applicant counts, company data, and related listings. This measures how well supported the score is, not whether the employer has guaranteed an interview.`,
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
    signals.push("Related openings appear to be active at the same time.");
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

function ScoreReasoningTooltip({ job }: { job: JobListItem }) {
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

function safeExternalUrl(value?: string | null): string | null {
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

function sourceLinks(job: JobListItem) {
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

function formatSalary(job: JobListItem): string | null {
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

export default function Home() {
  const [jobs, setJobs] = useState<JobListItem[]>([]);
  const [totalResults, setTotalResults] = useState<number | null>(null);
  const [totalPages, setTotalPages] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [q, setQ] = useState("");
  const [jobFamily, setJobFamily] = useState("");
  const [jobBoard, setJobBoard] = useState("");
  const [applicantMax, setApplicantMax] = useState("");
  const [seniority, setSeniority] = useState("");
  const [employmentType, setEmploymentType] = useState("");
  const [remoteType, setRemoteType] = useState("");
  const [classification, setClassification] = useState("");
  const [clearanceRequired, setClearanceRequired] = useState("");
  const [sortBy, setSortBy] = useState("active_hiring_confidence");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [collapseCanonical, setCollapseCanonical] = useState(true);
  const [includeOlderJobs, setIncludeOlderJobs] = useState(false);

  async function load(
    targetPage = 1,
    scrollAfterLoad = false,
    overrides?: {
      collapseCanonical?: boolean;
      includeOlderJobs?: boolean;
    },
  ) {
    if (targetPage < 1) return;

    setLoading(true);
    setError(null);

    try {
      const data = await jobsApi.list({
        page: targetPage,
        page_size: PAGE_SIZE,
        q: q || undefined,
        job_family: jobFamily || undefined,
        job_board: jobBoard || undefined,
        applicant_max: applicantMax ? Number(applicantMax) : undefined,
        max_age_days:
          (overrides?.includeOlderJobs ?? includeOlderJobs)
            ? undefined
            : DEFAULT_MAX_AGE_DAYS,
        seniority: seniority || undefined,
        employment_type: employmentType || undefined,
        remote_type: remoteType || undefined,
        classification: classification || undefined,
        clearance_required:
          clearanceRequired === "" ? undefined : clearanceRequired === "true",
        collapse_canonical: overrides?.collapseCanonical ?? collapseCanonical,
        sort_by: sortBy,
        sort_dir: sortDir,
      });

      setJobs(data.results);
      setTotalResults(data.total);
      setTotalPages(data.pages);
      setPage(data.page);

      if (scrollAfterLoad) {
        window.requestAnimationFrame(() => {
          window.scrollTo({
            top: 0,
            behavior: "smooth",
          });
        });
      }
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to load jobs");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load(1);
    // Initial load only; filter changes are applied when the search form is submitted.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const firstVisibleResult = totalResults && jobs.length > 0 ? (page - 1) * PAGE_SIZE + 1 : 0;
  const lastVisibleResult = totalResults
    ? Math.min((page - 1) * PAGE_SIZE + jobs.length, totalResults)
    : 0;

  return (
    <>
      <Head>
        <title>JobLens | Active Hiring Confidence</title>
        <meta
          name="description"
          content="Posting history and active hiring signals for technology roles."
        />
      </Head>

      <main className="min-h-screen bg-slate-950 text-slate-100">
        <section className="mx-auto max-w-5xl px-6 py-20">
          <p className="mb-3 text-sm font-semibold uppercase tracking-[0.22em] text-cyan-300">
            JobLens
          </p>

          <h1 className="max-w-3xl text-4xl font-bold tracking-tight sm:text-6xl">
            Find jobs more likely to be actively hiring.
          </h1>

          <p className="mt-6 max-w-3xl text-lg leading-8 text-slate-300">
            Active Hiring Confidence uses posting age, repeated observations, parallel openings,
            repost history, compensation, and applicant signals. It is an estimate, not a guarantee
            of employer intent. This tool is intended as a supplement to your research and judgment,
            not a replacement for it. Always verify the information and use your own discretion when
            applying for jobs.
          </p>

          <p className="mt-3 text-slate-400">
            Active Hiring Confidence (Ghost Job Filtering) · Repost tracking · Salary transparency
          </p>

          <form
            className="mt-8 grid gap-4 rounded-xl border border-slate-800 bg-slate-900/60 p-4 sm:grid-cols-2 lg:grid-cols-4"
            onSubmit={(event) => {
              event.preventDefault();
              void load(1);
            }}
          >
            <input
              aria-label="Search jobs"
              value={q}
              onChange={(event) => setQ(event.target.value)}
              placeholder="Search title, company, city, or state"
              className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100 placeholder:text-slate-500"
            />

            <select
              aria-label="Role type"
              value={jobFamily}
              onChange={(event) => setJobFamily(event.target.value)}
              className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100"
            >
              <option value="">All role types</option>
              <option value="data analyst">Data analyst</option>
              <option value="data scientist">Data scientist</option>
              <option value="data engineer">Data engineer</option>
              <option value="software engineer">Software engineer</option>
              <option value="machine learning engineer">Machine learning engineer</option>
              <option value="business analyst">Business analyst</option>
              <option value="product manager">Product manager</option>
              <option value="technical program manager">Technical program manager</option>
              <option value="project manager">Project manager</option>
            </select>

            <div className="flex flex-col">
              <input
                aria-label="Max reported applicants"
                value={applicantMax}
                onChange={(event) => setApplicantMax(event.target.value)}
                placeholder="Max reported applicants"
                type="number"
                min="0"
                className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100 placeholder:text-slate-500"
              />

              {applicantMax && (
                <p role="note" className="mt-1.5 text-xs leading-5 text-amber-400">
                  Jobs with unavailable applicant count data are included in these results.
                </p>
              )}
            </div>

            <select
              aria-label="Job board"
              value={jobBoard}
              onChange={(event) => setJobBoard(event.target.value)}
              className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100"
            >
              <option value="">All job boards</option>
              <option value="company_site">Company site</option>
              <option value="linkedin">LinkedIn</option>
              <option value="indeed">Indeed</option>
              <option value="glassdoor">Glassdoor</option>
              <option value="ziprecruiter">ZipRecruiter</option>
              <option value="dice">Dice</option>
              <option value="monster">Monster</option>
              <option value="jobright">Jobright</option>
              <option value="simplify">Simplify</option>
            </select>

            <select
              aria-label="Seniority"
              value={seniority}
              onChange={(event) => setSeniority(event.target.value)}
              className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100"
            >
              <option value="">All seniority</option>
              <option value="Entry">Entry</option>
              <option value="Mid">Mid</option>
              <option value="Senior">Senior</option>
              <option value="Lead">Lead</option>
              <option value="Executive">Executive</option>
            </select>

            <select
              aria-label="Employment type"
              value={employmentType}
              onChange={(event) => setEmploymentType(event.target.value)}
              className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100"
            >
              <option value="">All employment types</option>
              <option value="Full-time">Full-time</option>
              <option value="Part-time">Part-time</option>
              <option value="Contract">Contract</option>
              <option value="Internship">Internship</option>
            </select>

            <select
              aria-label="Work arrangement"
              value={remoteType}
              onChange={(event) => setRemoteType(event.target.value)}
              className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100"
            >
              <option value="">All work types</option>
              <option value="Remote">Remote</option>
              <option value="Hybrid">Hybrid</option>
              <option value="Onsite">Onsite</option>
            </select>

            <select
              aria-label="Listing classification"
              value={classification}
              onChange={(event) => setClassification(event.target.value)}
              className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100"
            >
              <option value="">All listing types</option>
              <option value="original">Original</option>
              <option value="parallel">Parallel</option>
              <option value="repost">Repost</option>
            </select>

            <select
              aria-label="Security clearance"
              title="Detected from the listing title text. This is a best-effort match and may not catch every clearance phrasing."
              value={clearanceRequired}
              onChange={(event) => setClearanceRequired(event.target.value)}
              className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100"
            >
              <option value="">Any clearance status</option>
              <option value="true">Clearance mentioned</option>
              <option value="false">No clearance mentioned</option>
            </select>

            <select
              aria-label="Sort jobs by"
              value={sortBy}
              onChange={(event) => setSortBy(event.target.value)}
              className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100"
            >
              <option value="active_hiring_confidence">Sort by confidence</option>
              <option value="date_posted">Sort by posting date</option>
              <option value="date_first_seen">Sort by newest seen</option>
              <option value="ghost_job_probability">Sort by ghost probability</option>
              <option value="health_score">Sort by health score</option>
              <option value="salary_max">Sort by salary</option>
              <option value="applicant_count">Sort by applicants</option>
            </select>

            <select
              aria-label="Sort direction"
              value={sortDir}
              onChange={(event) => setSortDir(event.target.value as "asc" | "desc")}
              className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100"
            >
              <option value="desc">High/new first</option>
              <option value="asc">Low/old first</option>
            </select>

            <label className="flex items-center gap-2 text-sm text-slate-300">
              <input
                type="checkbox"
                checked={collapseCanonical}
                onChange={(event) => {
                  const nextValue = event.target.checked;
                  setCollapseCanonical(nextValue);
                  void load(1, false, { collapseCanonical: nextValue });
                }}
                className="h-4 w-4"
              />
              Collapse related listings
            </label>

            <label className="flex items-center gap-2 text-sm text-slate-300">
              <input
                type="checkbox"
                checked={includeOlderJobs}
                onChange={(event) => {
                  const nextValue = event.target.checked;
                  setIncludeOlderJobs(nextValue);
                  void load(1, false, { includeOlderJobs: nextValue });
                }}
                className="h-4 w-4"
              />
              Include jobs posted over {DEFAULT_MAX_AGE_DAYS} days ago
            </label>

            <button
              type="submit"
              disabled={loading}
              className="rounded-lg bg-cyan-300 px-5 py-3 font-semibold text-slate-950 disabled:opacity-60 sm:col-span-2 lg:col-span-4"
            >
              {loading ? "Loading…" : "Search jobs"}
            </button>
          </form>

          {error && (
            <p className="mt-4 rounded-lg border border-red-500/40 bg-red-950/40 p-4 text-red-200">
              {error}
            </p>
          )}

          {!loading && !error && totalResults !== null && (
            <div
              className="mt-8 rounded-lg border border-slate-800 bg-slate-900/70 p-4 text-sm text-slate-300"
              role="status"
              aria-live="polite"
            >
              {totalResults > 0 ? (
                <p>
                  Showing {firstVisibleResult}–{lastVisibleResult} of {totalResults} result
                  {totalResults === 1 ? "" : "s"}. Page {page} of {Math.max(totalPages, 1)}.
                  {collapseCanonical
                    ? " Related listings are grouped."
                    : " Each active listing is shown separately."}
                  {!includeOlderJobs
                    ? ` Listings posted more than ${DEFAULT_MAX_AGE_DAYS} days ago are hidden.`
                    : " Older listings are included."}
                </p>
              ) : (
                <p>
                  No results found. Try clearing one or more filters, increasing the max reported
                  applicants value, or searching a broader city, state, title, or company.
                </p>
              )}
            </div>
          )}

          {!loading && !error && totalResults !== null && totalResults > 0 && totalPages > 1 && (
            <nav
              aria-label="Top job results pagination"
              className="mt-4 flex items-center justify-between gap-4 rounded-lg border border-slate-800 bg-slate-900/50 p-3"
            >
              <button
                type="button"
                onClick={() => load(page - 1, true)}
                disabled={page <= 1 || loading}
                className="rounded-lg border border-slate-700 bg-slate-900 px-4 py-2 text-sm font-semibold text-slate-200 transition hover:border-cyan-300 hover:text-cyan-200 disabled:cursor-not-allowed disabled:opacity-40"
              >
                Previous
              </button>

              <p className="text-sm text-slate-400">
                Page {page} of {totalPages}
              </p>

              <button
                type="button"
                onClick={() => load(page + 1, true)}
                disabled={page >= totalPages || loading}
                className="rounded-lg border border-slate-700 bg-slate-900 px-4 py-2 text-sm font-semibold text-slate-200 transition hover:border-cyan-300 hover:text-cyan-200 disabled:cursor-not-allowed disabled:opacity-40"
              >
                Next
              </button>
            </nav>
          )}

          {loading && jobs.length === 0 && (
            <div className="mt-10 grid gap-4" aria-label="Loading jobs">
              {Array.from({ length: 5 }).map((_, index) => (
                <div
                  key={index}
                  className="h-36 animate-pulse rounded-xl border border-slate-800 bg-slate-900/70"
                />
              ))}
            </div>
          )}

          {!loading && !error && totalResults === 0 && (
            <div className="mt-10 rounded-xl border border-slate-800 bg-slate-900/70 p-6 text-center text-slate-300">
              No jobs match these filters. Try a broader search or clear one or more filters.
            </div>
          )}

          <div className="mt-10 grid gap-4">
            {jobs.map((job) => {
              const salary = formatSalary(job);
              const confidence = job.active_hiring_confidence;

              return (
                <article
                  key={job.id}
                  className="rounded-xl border border-slate-800 bg-slate-900/70 p-5"
                >
                  <div className="flex flex-col justify-between gap-4 sm:flex-row">
                    <div>
                      <h2 className="text-xl font-semibold">{job.title_raw}</h2>

                      <p className="mt-1 text-slate-300">
                        {job.company.name} ·{" "}
                        {job.location_raw || job.remote_type || "Location unavailable"}
                      </p>

                      <p className="mt-1 text-sm text-slate-400">
                        {job.job_family || "Unknown role type"}
                        {job.seniority ? ` · ${job.seniority}` : ""}
                        {job.employment_type ? ` · ${job.employment_type}` : ""}
                        {job.remote_type ? ` · ${job.remote_type}` : ""}
                      </p>

                      <p className="mt-2 text-sm text-slate-400">
                        {job.listing_classification}
                        {job.repost_count > 0 ? ` · repost #${job.repost_count}` : ""}
                        {` · ${ageSummary(job)}`}
                        {job.applicant_count != null
                          ? ` · ${job.applicant_count} reported applicants`
                          : ""}
                        {salary ? ` · ${salary}` : ""}
                      </p>

                      <div className="mt-3 flex flex-wrap items-center gap-2 text-sm">
                        <span className="text-slate-400">Found on</span>

                        {sourceLinks(job).map(({ source, label }) => {
                          const safeUrl = safeExternalUrl(source.source_url);

                          return safeUrl ? (
                            <a
                              key={source.sighting_key}
                              href={safeUrl}
                              target="_blank"
                              rel="noopener noreferrer"
                              title={`Open this listing on ${source.publisher_name}`}
                              className="rounded-full border border-cyan-500/40 bg-cyan-950/30 px-3 py-1 text-cyan-200 hover:border-cyan-300"
                            >
                              {label}
                              {source.is_direct ? " · Direct" : ""}
                            </a>
                          ) : (
                            <span
                              key={source.sighting_key}
                              title="The source URL was unavailable or invalid"
                              className="rounded-full border border-slate-700 px-3 py-1 text-slate-300"
                            >
                              {label}
                              {source.is_direct ? " · Direct" : ""}
                            </span>
                          );
                        })}
                      </div>
                    </div>

                    <ScoreReasoningTooltip job={job} />
                  </div>
                </article>
              );
            })}
          </div>

          {!loading && !error && totalResults !== null && totalResults > 0 && totalPages > 1 && (
            <nav
              aria-label="Job results pagination"
              className="mt-8 flex items-center justify-between gap-4"
            >
              <button
                type="button"
                onClick={() => load(page - 1, true)}
                disabled={page <= 1 || loading}
                className="rounded-lg border border-slate-700 bg-slate-900 px-4 py-2 text-sm font-semibold text-slate-200 transition hover:border-cyan-300 hover:text-cyan-200 disabled:cursor-not-allowed disabled:opacity-40"
              >
                Previous
              </button>

              <p className="text-sm text-slate-400">
                Page {page} of {totalPages}
              </p>

              <button
                type="button"
                onClick={() => load(page + 1, true)}
                disabled={page >= totalPages || loading}
                className="rounded-lg border border-slate-700 bg-slate-900 px-4 py-2 text-sm font-semibold text-slate-200 transition hover:border-cyan-300 hover:text-cyan-200 disabled:cursor-not-allowed disabled:opacity-40"
              >
                Next
              </button>
            </nav>
          )}
        </section>
      </main>
    </>
  );
}