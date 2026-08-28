import Head from "next/head";
import Link from "next/link";

import { Logo } from "@/components/Logo";
import { PAGE_TITLE } from "@/lib/typography";

export default function NotFoundPage() {
  return (
    <>
      <Head>
        <title>Page not found | JobLens</title>
        <meta name="robots" content="noindex" />
      </Head>

      <section className="mx-auto flex max-w-xl flex-col items-center px-6 py-24 text-center">
        <Logo className="text-2xl" />

        <h1 className={`mt-8 ${PAGE_TITLE}`}>Sorry, no jobs here.</h1>

        <p className="mt-4 text-slate-300">
          The page you followed does not exist, or the link is out of date. It is not a listing
          JobLens has tracked, and it does not mean any positions you are watching have closed.
        </p>

        <Link
          href="/"
          className="mt-8 rounded-lg bg-cyan-600 px-5 py-2.5 font-medium text-slate-950 outline-none ring-cyan-300 transition hover:bg-cyan-500 focus-visible:ring-2"
        >
          Back to job search
        </Link>
      </section>
    </>
  );
}
