import Link from "next/link";
import { useRouter } from "next/router";
import type { ReactNode } from "react";

import { Logo } from "@/components/Logo";

interface NavLink {
  href: string;
  label: string;
  isActive: (pathname: string, tab: string | undefined) => boolean;
}

const NAV_LINKS: NavLink[] = [
  {
    href: "/",
    label: "Job Search",
    isActive: (pathname) => pathname === "/",
  },
  {
    href: "/profile",
    label: "Profile",
    isActive: (pathname) => pathname === "/profile",
  },
];

export function Layout({ children }: { children: ReactNode }) {
  const router = useRouter();
  const tab = typeof router.query.tab === "string" ? router.query.tab : undefined;

  return (
    <div className="flex min-h-screen flex-col bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800">
        <div className="mx-auto flex max-w-[90rem] flex-wrap items-center justify-between gap-4 px-6 py-4">
          <Link href="/" className="shrink-0 rounded-lg outline-none ring-cyan-300 focus-visible:ring-2">
            <Logo showTagline className="text-xl sm:text-2xl" />
          </Link>

          <nav aria-label="Primary" className="flex flex-wrap items-center gap-1 text-sm font-medium">
            {NAV_LINKS.map((link) => {
              const active = link.isActive(router.pathname, tab);
              return (
                <Link
                  key={link.label}
                  href={link.href}
                  aria-current={active ? "page" : undefined}
                  className={`rounded-lg px-3 py-2 outline-none ring-cyan-300 transition focus-visible:ring-2 ${
                    active
                      ? "bg-slate-800 text-cyan-200"
                      : "text-slate-300 hover:bg-slate-900 hover:text-slate-100"
                  }`}
                >
                  {link.label}
                </Link>
              );
            })}
          </nav>
        </div>
      </header>

      <main className="flex-1">{children}</main>

      <footer className="border-t border-slate-800">
        <div className="mx-auto flex max-w-[90rem] flex-col gap-3 px-6 py-6 text-sm text-slate-400 sm:flex-row sm:items-center sm:justify-between">
          <p className="max-w-xl">
            JobLens helps you tell current, actively hiring job listings apart from stale,
            recycled, duplicated, or uncertain ones.
          </p>
          <p>
            Company logos by{" "}
            <a
              href="https://logos.apistemic.com"
              target="_blank"
              rel="noopener"
              className="font-medium text-slate-300 underline decoration-slate-600 underline-offset-2 hover:text-cyan-200"
            >
              apistemic logos
            </a>
          </p>
        </div>
      </footer>
    </div>
  );
}
