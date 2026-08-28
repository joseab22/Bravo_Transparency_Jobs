import Head from "next/head";
import Link from "next/link";

import { PAGE_TITLE, SECTION_TITLE } from "@/lib/typography";
import { SITE_URL } from "@/lib/seo";

const LAST_UPDATED = "August 26, 2026";

export default function TermsOfService() {
  return (
    <>
      <Head>
        <title>Terms of Service | JobLens</title>
        <meta
          name="description"
          content="The terms governing use of JobLens, including that JobLens is not the employer and does not control third-party application platforms."
        />
        <link rel="canonical" href={`${SITE_URL}/terms`} />
      </Head>

      <section className="mx-auto max-w-[90rem] px-6 py-12">
        <div className="max-w-3xl">
          <h1 className={PAGE_TITLE}>Terms of Service</h1>
          <p className="mt-2 text-sm text-slate-400">Last updated: {LAST_UPDATED}</p>

          <p className="mt-8 leading-7 text-slate-300">
            By using JobLens, you agree to these terms. If you do not agree, do not use the site.
          </p>

          <h2 className={`mt-10 ${SECTION_TITLE}`}>What JobLens is</h2>
          <p className="mt-3 leading-7 text-slate-300">
            JobLens is a job-market transparency tool. It collects job postings from third-party
            sources, tracks their history, and estimates how likely a listing is to represent an
            actively hiring role. JobLens is not a recruiter, staffing agency, or employer, does not
            place candidates, and does not process job applications itself.
          </p>

          <h2 className={`mt-10 ${SECTION_TITLE}`}>Estimates, not guarantees</h2>
          <p className="mt-3 leading-7 text-slate-300">
            Active-hiring confidence scores, listing classifications, and any other assessment shown
            on JobLens are estimates based on public signals such as posting age, repost history, and
            reported applicant counts. They are not verified with employers and are not a guarantee
            that a position is open, that an employer intends to hire, or that you will be interviewed
            or hired. Always verify a listing independently and use your own judgment before applying
            or making decisions based on it.
          </p>

          <h2 className={`mt-10 ${SECTION_TITLE}`}>Third-party platforms and applying to jobs</h2>
          <p className="mt-3 leading-7 text-slate-300">
            Every listing on JobLens links out to the employer&apos;s own site or a third-party job
            board where the actual application takes place. JobLens does not operate, control, or
            vouch for those sites.{" "}
            <span className="font-semibold text-slate-100">
              Any information you submit when you apply, and any account you create, on one of those
              platforms is governed entirely by that platform&apos;s own terms of service and privacy
              policy
            </span>
            , not JobLens&apos;s. See our{" "}
            <Link href="/privacy" className="text-cyan-300 underline decoration-slate-600 underline-offset-2 hover:text-cyan-200">
              Privacy Policy
            </Link>{" "}
            for more on this.
          </p>

          <h2 className={`mt-10 ${SECTION_TITLE}`}>No account, device-based data</h2>
          <p className="mt-3 leading-7 text-slate-300">
            JobLens does not require registration. Features like favorites, notes, and application
            tracking are tied to an anonymous identifier stored in your browser rather than to an
            account. You are responsible for your own device and browser; JobLens cannot recover this
            data if it is lost (for example, by clearing browser storage or switching devices).
          </p>

          <h2 className={`mt-10 ${SECTION_TITLE}`}>Acceptable use</h2>
          <p className="mt-3 leading-7 text-slate-300">
            You agree not to misuse JobLens, including by attempting to disrupt the service, bypass
            rate limits or access controls, or scrape the site at a volume that degrades it for other
            users.
          </p>

          <h2 className={`mt-10 ${SECTION_TITLE}`}>Job listing content</h2>
          <p className="mt-3 leading-7 text-slate-300">
            Job listing content displayed on JobLens originates from the employers and platforms that
            posted it and remains their property. JobLens aggregates and annotates this content; it
            does not claim ownership of the underlying postings.
          </p>

          <h2 className={`mt-10 ${SECTION_TITLE}`}>Disclaimer of warranties</h2>
          <p className="mt-3 leading-7 text-slate-300">
            JobLens is provided &ldquo;as is&rdquo; and &ldquo;as available,&rdquo; without warranties
            of any kind, express or implied, including accuracy, completeness, or availability of any
            listing or score at any given time.
          </p>

          <h2 className={`mt-10 ${SECTION_TITLE}`}>Limitation of liability</h2>
          <p className="mt-3 leading-7 text-slate-300">
            To the maximum extent permitted by law, JobLens is not liable for any decision made, or
            harm suffered, in reliance on information shown on the site, or for the actions of any
            third-party platform you are directed to.
          </p>

          <h2 className={`mt-10 ${SECTION_TITLE}`}>Changes to these terms</h2>
          <p className="mt-3 leading-7 text-slate-300">
            These terms may be updated as JobLens changes. Material changes will update the &ldquo;Last
            updated&rdquo; date above. Continued use after a change means you accept the updated terms.
          </p>

          <h2 className={`mt-10 ${SECTION_TITLE}`}>Governing law</h2>
          <p className="mt-3 leading-7 text-slate-300">
            These terms are governed by the laws of the{" "}
            <span className="font-semibold text-slate-100">United States</span>.
          </p>

          <h2 className={`mt-10 ${SECTION_TITLE}`}>Contact</h2>
          <p className="mt-3 leading-7 text-slate-300">
            Questions about these terms can be sent to{" "}
            <a
              href="mailto:deljosebravoalfonso@gmail.com"
              className="font-semibold text-cyan-300 underline decoration-slate-600 underline-offset-2 hover:text-cyan-200"
            >
              deljosebravoalfonso@gmail.com
            </a>
            .
          </p>
        </div>
      </section>
    </>
  );
}
