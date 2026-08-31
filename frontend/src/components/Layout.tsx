import Link from "next/link";
import { useRouter } from "next/router";
import type { ReactNode } from "react";

import { Logo } from "@/components/Logo";
import { ThemeToggle } from "@/components/ThemeToggle";

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
    <div className="flex min-h-screen flex-col bg-page text-ink-primary">
      <header className="border-b border-line-subtle">
        <div className="mx-auto flex max-w-[90rem] flex-wrap items-center justify-between gap-4 px-6 py-4">
          <Link href="/" className="shrink-0 rounded-lg outline-none ring-accent focus-visible:ring-2">
            <Logo showTagline className="text-xl sm:text-2xl" />
          </Link>

          <div className="flex flex-wrap items-center gap-1">
            <nav aria-label="Primary" className="flex flex-wrap items-center gap-1 text-sm font-medium">
              {NAV_LINKS.map((link) => {
                const active = link.isActive(router.pathname, tab);
                return (
                  <Link
                    key={link.label}
                    href={link.href}
                    aria-current={active ? "page" : undefined}
                    className={`rounded-lg px-3 py-2 outline-none ring-accent transition focus-visible:ring-2 ${
                      active
                        ? "bg-surface-2 text-accent"
                        : "text-ink-secondary hover:bg-surface hover:text-ink-primary"
                    }`}
                  >
                    {link.label}
                  </Link>
                );
              })}
            </nav>
            <ThemeToggle />
          </div>
        </div>
      </header>

      <main className="flex-1">{children}</main>

      <footer className="border-t border-line-subtle">
        <div className="mx-auto flex max-w-[90rem] flex-col gap-3 px-6 py-6 text-sm text-ink-muted sm:flex-row sm:items-center sm:justify-between">
          <p className="max-w-xl">
            JobLens helps you tell current, actively hiring job listings apart from stale,
            recycled, duplicated, or uncertain ones.
          </p>

          <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
            <Link
              href="/terms"
              className="rounded font-medium text-ink-secondary underline decoration-line underline-offset-2 outline-none ring-accent hover:text-accent focus-visible:ring-2"
            >
              Terms of Service
            </Link>
            <Link
              href="/privacy"
              className="rounded font-medium text-ink-secondary underline decoration-line underline-offset-2 outline-none ring-accent hover:text-accent focus-visible:ring-2"
            >
              Privacy Policy
            </Link>
            <p>
              Company logos by{" "}
              <a
                href="https://logos.apistemic.com"
                target="_blank"
                rel="noopener"
                className="font-medium text-ink-secondary underline decoration-line underline-offset-2 hover:text-accent"
              >
                apistemic logos
              </a>
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}
