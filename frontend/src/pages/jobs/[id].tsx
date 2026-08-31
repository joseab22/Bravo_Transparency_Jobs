import { useEffect, useState } from "react";
import type { GetServerSideProps } from "next";
import Head from "next/head";
import Link from "next/link";

import { JobDetailContent } from "@/components/JobDetailPanel";
import { Logo } from "@/components/Logo";
import { jobsApi, meApi } from "@/lib/api";
import { formatSalary } from "@/lib/jobFormatting";
import { SITE_URL } from "@/lib/seo";
import type { JobDetail } from "@/types/jobs";

interface JobPageProps {
  job: JobDetail | null;
}

// Server-side fetch hits the backend directly (BACKEND_INTERNAL_URL), not
// through jobsApi's browser fetch + Next rewrite -- rewrites only apply to
// incoming requests the Next server receives, not outgoing fetches it makes
// itself during SSR. No device_id is available server-side either way (no
// localStorage), so this intentionally returns unpersonalized data; the
// client reconciles favorite/applied/note state after mount, same pattern
// JobDetailPanel already uses for the in-list detail view.
export const getServerSideProps: GetServerSideProps<JobPageProps> = async ({ params, res }) => {
  const id = Number(params?.id);
  if (!Number.isFinite(id) || id <= 0) {
    res.statusCode = 404;
    return { props: { job: null } };
  }

  const backend = (process.env.BACKEND_INTERNAL_URL || "http://backend:8000").replace(/\/$/, "");

  try {
    const response = await fetch(`${backend}/api/v1/jobs/${id}`);
    if (!response.ok) {
      res.statusCode = response.status === 404 ? 404 : 502;
      return { props: { job: null } };
    }
    const job = (await response.json()) as JobDetail;
    return { props: { job } };
  } catch {
    res.statusCode = 502;
    return { props: { job: null } };
  }
};

export default function JobPage({ job: initialJob }: JobPageProps) {
  const [job, setJob] = useState<JobDetail | null>(initialJob);

  // Reconcile device-scoped personalization (favorite/applied/note) after
  // mount -- the SSR fetch above has no access to the browser's device ID.
  useEffect(() => {
    if (!initialJob) return;
    let cancelled = false;

    void meApi.recordView(initialJob.id).catch(() => {
      // Recording a view is a soft signal; a failure here shouldn't block the page.
    });

    jobsApi
      .get(initialJob.id)
      .then((fresh) => {
        if (!cancelled) setJob(fresh);
      })
      .catch(() => {
        // Keep the SSR-rendered (unpersonalized) job on failure.
      });

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialJob?.id]);

  if (!job) {
    return (
      <section className="mx-auto flex max-w-xl flex-col items-center px-6 py-24 text-center">
        <Logo className="text-2xl" />
        <h1 className="mt-8 text-3xl font-bold tracking-tight">Listing not found</h1>
        <p className="mt-4 text-ink-secondary">
          This job may have been removed, or the link may be incorrect.
        </p>
        <Link
          href="/"
          className="mt-8 rounded-lg bg-accent-solid px-5 py-2.5 font-medium text-ink-onaccent outline-none ring-accent transition hover:bg-accent-solid-hover focus-visible:ring-2"
        >
          Back to job search
        </Link>
      </section>
    );
  }

  const canonicalUrl = `${SITE_URL}/jobs/${job.id}`;
  const salary = formatSalary(job);
  const jsonLd: Record<string, unknown> = {
    "@context": "https://schema.org",
    "@type": "JobPosting",
    title: job.title_raw,
    description: job.description_raw || job.title_raw,
    datePosted: job.date_posted || job.date_first_seen,
    hiringOrganization: {
      "@type": "Organization",
      name: job.company.name,
    },
    employmentType: job.employment_type || undefined,
    jobLocationType: job.remote_type === "remote" ? "TELECOMMUTE" : undefined,
    ...(job.location_raw
      ? { jobLocation: { "@type": "Place", address: { "@type": "PostalAddress", addressLocality: job.location_raw } } }
      : {}),
    ...(salary && job.salary_min != null
      ? {
          baseSalary: {
            "@type": "MonetaryAmount",
            currency: job.salary_currency || "USD",
            value: { "@type": "QuantitativeValue", minValue: job.salary_min, maxValue: job.salary_max ?? job.salary_min, unitText: "YEAR" },
          },
        }
      : {}),
  };

  return (
    <>
      <Head>
        <title>{`${job.title_raw} at ${job.company.name} | JobLens`}</title>
        <meta
          name="description"
          content={`${job.title_raw} at ${job.company.name}${job.location_raw ? ` in ${job.location_raw}` : ""}. Active-hiring confidence and posting history tracked by JobLens.`}
        />
        <link rel="canonical" href={canonicalUrl} />
        <script
          type="application/ld+json"
          // eslint-disable-next-line react/no-danger
          dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
        />
      </Head>

      <section className="mx-auto max-w-3xl px-6 py-12">
        <JobDetailContent job={job} loadingMore={false} error={null} />
      </section>
    </>
  );
}
