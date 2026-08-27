import Head from "next/head";
import { useRouter } from "next/router";
import type { ReactElement } from "react";

import { ApplicationsTab } from "@/components/profile/ApplicationsTab";
import { FavoritesTab } from "@/components/profile/FavoritesTab";
import { HiddenTab } from "@/components/profile/HiddenTab";
import { NotesTab } from "@/components/profile/NotesTab";
import { RecentTab } from "@/components/profile/RecentTab";

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
      </Head>

      <section className="mx-auto max-w-[90rem] px-6 py-12">
        <div className="max-w-4xl">
          <h1 className="text-3xl font-bold tracking-tight">Your profile</h1>
          <p className="mt-2 max-w-2xl text-slate-300">
            Track the jobs you care about: what you have saved, what you have applied to, and
            where you left off.
          </p>

          <div
            role="tablist"
            aria-label="Profile sections"
            className="mt-8 flex flex-wrap gap-2 border-b border-slate-800 pb-3"
          >
            {TABS.map((tab) => (
              <button
                key={tab.key}
                type="button"
                role="tab"
                aria-selected={tab.key === activeTab}
                onClick={() => selectTab(tab.key)}
                className={`rounded-lg px-4 py-2 text-sm font-semibold outline-none ring-cyan-300 transition focus-visible:ring-2 ${
                  tab.key === activeTab
                    ? "bg-cyan-300 text-slate-950"
                    : "border border-slate-700 text-slate-300 hover:border-cyan-300 hover:text-cyan-200"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          <p className="mt-4 text-sm text-slate-400">{active.description}</p>

          <div role="tabpanel" className="mt-4">
            <ActiveTabContent />
          </div>
        </div>
      </section>
    </>
  );
}
