import Head from "next/head";
import Link from "next/link";

import { PAGE_TITLE, SECTION_TITLE } from "@/lib/typography";
import { SITE_URL } from "@/lib/seo";

// Static content with no per-request personalization, but kept as a real
// page (not automatically statically optimized) is unnecessary here -- this
// page has no useRouter() call, so it prerenders fine. No getServerSideProps
// needed, unlike /profile.

const LAST_UPDATED = "August 26, 2026";

export default function PrivacyPolicy() {
  return (
    <>
      <Head>
        <title>Privacy Policy | JobLens</title>
        <meta
          name="description"
          content="What JobLens collects, what it does not, and how your data is handled when you apply through a listing."
        />
        <link rel="canonical" href={`${SITE_URL}/privacy`} />
      </Head>

      <section className="mx-auto max-w-[90rem] px-6 py-12">
        <div className="max-w-3xl">
          <h1 className={PAGE_TITLE}>Privacy Policy</h1>
          <p className="mt-2 text-sm text-slate-400">Last updated: {LAST_UPDATED}</p>

          <div className="mt-8 rounded-xl border border-amber-700/40 bg-amber-950/20 p-4 text-sm leading-6 text-amber-100">
            This policy describes what JobLens itself collects and does with data. It does not, and
            cannot, describe the data practices of the employers and job boards you are redirected to
            when you apply. See &ldquo;When you apply&rdquo; below.
          </div>

          <h2 className={`mt-10 ${SECTION_TITLE}`}>Overview</h2>
          <p className="mt-3 leading-7 text-slate-300">
            JobLens does not require an account. There is no sign-up, no email address, no password,
            and no name collected to use the site. Instead, your browser generates a random,
            anonymous identifier (a &ldquo;device ID&rdquo;) the first time you visit, stores it in your
            browser&apos;s local storage, and sends it with requests so JobLens can remember things like
            your favorites across visits. JobLens has no way to connect that identifier to your real
            identity.
          </p>

          <h2 className={`mt-10 ${SECTION_TITLE}`}>Data we collect</h2>
          <ul className="mt-3 list-disc space-y-2 pl-5 leading-7 text-slate-300">
            <li>
              <span className="font-semibold text-slate-100">Device ID:</span> a random identifier
              generated in your browser, not derived from any personal information.
            </li>
            <li>
              <span className="font-semibold text-slate-100">Actions tied to that device ID:</span>{" "}
              jobs you favorite, mark as applied (including any status or notes you type into the
              Applications tab), add a personal note to, hide from search results, or save a search
              filter for. Also, a short list of listings you have recently viewed.
            </li>
            <li>
              <span className="font-semibold text-slate-100">Standard server logs:</span> like most
              web services, JobLens&apos;s infrastructure may log basic request metadata (timestamps, IP
              address, requested URL) for security and reliability purposes.
            </li>
          </ul>

          <h2 className={`mt-10 ${SECTION_TITLE}`}>Data we do not collect</h2>
          <p className="mt-3 leading-7 text-slate-300">
            JobLens does not use cookies, does not use third-party analytics or advertising trackers,
            and does not ask for your name, email address, phone number, resume, or any payment
            information. JobLens never asks you to submit a job application through JobLens itself.
          </p>

          <h2 className={`mt-10 ${SECTION_TITLE}`}>Job listing data</h2>
          <p className="mt-3 leading-7 text-slate-300">
            The job postings shown on JobLens are collected from third-party job data providers and
            publicly available listings, not submitted by JobLens users. Company logos are loaded from
            a third-party logo service at request time. Active-hiring confidence scores are an
            estimate JobLens calculates from public signals like posting age and repost history; they
            are not a guarantee of an employer&apos;s intent to hire.
          </p>

          <h2 className={`mt-10 ${SECTION_TITLE}`}>When you apply</h2>
          <p className="mt-3 leading-7 text-slate-300">
            Clicking &ldquo;Apply&rdquo; or a source link on a listing takes you to the employer&apos;s
            website or a third-party job board, outside of JobLens. Any information you submit there
            &mdash; your resume, contact details, application answers, or anything else &mdash; is
            <span className="font-semibold text-slate-100">
              {" "}
              subject entirely to that platform&apos;s own privacy policy and terms
            </span>
            , not this one. JobLens does not receive, see, or store anything you submit on those
            external sites, and has no control over how they handle your information. Review the
            privacy policy of each site before applying.
          </p>

          <h2 className={`mt-10 ${SECTION_TITLE}`}>Deleting your data</h2>
          <p className="mt-3 leading-7 text-slate-300">
            You can remove any favorite, application, note, or saved search directly from your{" "}
            <Link href="/profile" className="text-cyan-300 underline decoration-slate-600 underline-offset-2 hover:text-cyan-200">
              profile
            </Link>{" "}
            page at any time. Clearing your browser&apos;s local storage (or using a different browser
            or device) generates a new, disconnected device ID and permanently severs access to the
            data tied to the old one from your side.
          </p>

          <h2 className={`mt-10 ${SECTION_TITLE}`}>Data retention</h2>
          <p className="mt-3 leading-7 text-slate-300">
            Job listing history is retained to preserve an accurate posting timeline even after a
            listing closes. Device-scoped data (favorites, applications, notes, dismissals, saved
            searches) is retained until you delete it or your device ID otherwise stops being sent.
          </p>

          <h2 className={`mt-10 ${SECTION_TITLE}`}>Children&apos;s privacy</h2>
          <p className="mt-3 leading-7 text-slate-300">
            JobLens is not directed at children and is not knowingly used to collect information from
            children.
          </p>

          <h2 className={`mt-10 ${SECTION_TITLE}`}>Changes to this policy</h2>
          <p className="mt-3 leading-7 text-slate-300">
            This policy may be updated as JobLens changes. Material changes will update the &ldquo;Last
            updated&rdquo; date above.
          </p>

          <h2 className={`mt-10 ${SECTION_TITLE}`}>Contact</h2>
          <p className="mt-3 leading-7 text-slate-300">
            Questions about this policy can be sent to{" "}
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
