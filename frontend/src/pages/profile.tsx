import type { GetServerSideProps } from "next";
import Head from "next/head";
import { useRouter } from "next/router";
import type { ReactElement } from "react";

import { ApplicationsTab } from "@/components/profile/ApplicationsTab";
import { FavoritesTab } from "@/components/profile/FavoritesTab";
import { HiddenTab } from "@/components/profile/HiddenTab";
import { NotesTab } from "@/components/profile/NotesTab";
import { RecentTab } from "@/components/profile/RecentTab";
import { SITE_URL } from "@/lib/seo";
import { PAGE_TITLE } from "@/lib/typography";

const TABS = [
  { key: "saved", label: "Saved Jobs", description: "Jobs you've favorited while browsing." },
  {
    key: "applications",
    label: "Applications",
    description: "Jobs you've marked as applied, along with status and notes.",
  },
  { key: "recent", label: "Recently Viewed", description: "Listings you've opened recently." },
  { key: "notes", label: "Notes", description: "Personal notes you've added to individual listings." },
  { key: "hidden", label: "Hidden", description: "Listings you've dismissed from search results." },
] as const;

type TabKey = (typeof TABS)[number]["key"];

const TAB_COMPONENTS: Record<TabKey, () => ReactElement> = {
  saved: FavoritesTab,
  applications: ApplicationsTab,
  recent: RecentTab,
  notes: NotesTab,
  hidden: HiddenTab,
};

// The page reads router.query.tab (a per-request value) to pick the active
// tab, so it can't be pre-rendered once at build time -- Next's automatic
// static optimization has no mounted router to satisfy useRouter() during
// that prerender pass, which fails the build with "NextRouter was not
// mounted". An empty getServerSideProps opts the page into per-request
// rendering instead, where the router is available. No props are needed;
// all real data (favorites, applications, etc.) is still fetched
// client-side per device via meApi, same as before.
export const getServerSideProps: GetServerSideProps = async () => {
  return { props: {} };
};

export default function Profile() {
  const router = useRouter();
  const requestedTab = typeof router.query.tab === "string" ? router.query.tab : undefined;
  const activeTab: TabKey = TABS.find((tab) => tab.key === requestedTab)?.key ?? "saved";
  const active = TABS.find((tab) => tab.key === activeTab)!;
  const ActiveTabContent = TAB_COMPONENTS[activeTab];

  function selectTab(key: TabKey) {
    void router.push({ pathname: "/profile", query: { tab: key } }, undefined, { shallow: true });
  }

  return (
    <>
      <Head>
        <title>Your Profile | JobLens</title>
        <meta
          name="description"
          content="Your saved jobs, applications, notes, and recently viewed listings on JobLens."
        />
        <link rel="canonical" href={`${SITE_URL}/profile`} />
        {/* Per-device data with no content of public value to searchers -- keep out of the index. */}
        <meta name="robots" content="noindex" />
      </Head>

      <section className="mx-auto max-w-[90rem] px-6 py-12">
        <div className="max-w-4xl">
          <h1 className={PAGE_TITLE}>Your profile</h1>
          <p className="mt-2 max-w-2xl text-ink-secondary">
            Track the jobs you care about: what you have saved, what you have applied to, and
            where you left off.
          </p>

          <div
            role="tablist"
            aria-label="Profile sections"
            className="mt-8 flex flex-wrap gap-2 border-b border-line-subtle pb-3"
          >
            {TABS.map((tab) => (
              <button
                key={tab.key}
                type="button"
                role="tab"
                aria-selected={tab.key === activeTab}
                onClick={() => selectTab(tab.key)}
                className={`rounded-lg px-4 py-2 text-sm font-semibold outline-none ring-accent transition focus-visible:ring-2 ${
                  tab.key === activeTab
                    ? "bg-accent-solid text-ink-onaccent"
                    : "border border-line text-ink-secondary hover:border-accent hover:text-accent"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          <p className="mt-4 text-sm text-ink-muted">{active.description}</p>

          <div role="tabpanel" className="mt-4">
            <ActiveTabContent />
          </div>
        </div>
      </section>
    </>
  );
}
