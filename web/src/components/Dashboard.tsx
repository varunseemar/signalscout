"use client";

import clsx from "clsx";
import { Download, Loader2, Newspaper, Radar, Sparkles, Target } from "lucide-react";
import { useCallback, useDeferredValue, useEffect, useState } from "react";
import useSWR from "swr";
import { useAccess } from "@/lib/access";
import { API_URL, fetcher, send, setAdminToken, toQuery, type Filters, type Icp, type Lead, type LeadStatus, type Stats } from "@/lib/api";
import { FilterRail, DEFAULT_FILTERS, STATUS_TABS } from "./FilterRail";
import { Header } from "./Header";
import { IcpModal } from "./IcpModal";
import { LeadDrawer } from "./LeadDrawer";
import { LeadTable } from "./LeadTable";
import { StatsBar } from "./StatsBar";
import { Button } from "./ui";

const SORTS: { label: string; value: Filters["sort"] }[] = [
  { label: "Best match", value: "score" },
  { label: "Most recent", value: "recent" },
  { label: "Largest round", value: "amount" },
  { label: "Name", value: "name" },
];

export default function Dashboard() {
  const [filters, setFilters] = useState<Filters>(DEFAULT_FILTERS);
  const deferred = useDeferredValue(filters);
  const [openId, setOpenId] = useState<number | null>(null);
  const [checked, setChecked] = useState<Set<number>>(new Set());
  const [icpOpen, setIcpOpen] = useState(false);

  const leadsKey = `/api/leads?${toQuery(deferred)}`;
  const { data: leads, isLoading, error, mutate: mutateLeads } = useSWR<{ total: number; items: Lead[] }>(leadsKey, fetcher, {
    keepPreviousData: true,
  });
  const { data: stats, mutate: mutateStats } = useSWR<Stats>("/api/stats", fetcher);
  const { data: icp, mutate: mutateIcp } = useSWR<{ icp: Icp; options: { sectors: string[]; stages: string[] } }>(
    "/api/icp",
    fetcher,
  );

  const { refresh: refreshAccess } = useAccess();
  const [slowStart, setSlowStart] = useState(false);

  // Owner login: visiting /?admin=KEY stores the key locally, then strips it from the URL
  useEffect(() => {
    const url = new URL(window.location.href);
    const key = url.searchParams.get("admin");
    if (key === null) return;
    setAdminToken(key || null);
    url.searchParams.delete("admin");
    window.history.replaceState(null, "", url.toString());
    refreshAccess();
  }, [refreshAccess]);

  // Free-tier API sleeps when idle; tell the visitor instead of showing an endless skeleton
  useEffect(() => {
    if (stats) return;
    const t = setTimeout(() => setSlowStart(true), 4000);
    return () => clearTimeout(t);
  }, [stats]);

  const refreshAll = useCallback(() => {
    mutateLeads();
    mutateStats();
  }, [mutateLeads, mutateStats]);

  async function setStatus(id: number, status: LeadStatus) {
    mutateLeads(
      (d) => d && { ...d, items: d.items.map((l) => (l.id === id ? { ...l, status } : l)) },
      { revalidate: false },
    );
    await send(`/api/leads/${id}`, "PATCH", { status });
    refreshAll();
  }

  function exportCsv() {
    const q = checked.size ? toQuery({ ids: [...checked], status: filters.status }) : toQuery(filters);
    window.open(`${API_URL}/api/export.csv?${q}`, "_blank");
  }

  const items = leads?.items ?? [];
  const noData = !isLoading && !error && stats?.leads === 0 && !filters.status.length;

  return (
    <div className="flex min-h-screen flex-col">
      <Header onOpenIcp={() => setIcpOpen(true)} onRunFinished={refreshAll} />

      <main className="mx-auto w-full max-w-[1500px] flex-1 space-y-5 px-4 py-6 sm:px-6">
        {slowStart && !stats && !error && (
          <div className="flex items-center gap-2.5 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
            <Loader2 className="h-4 w-4 shrink-0 animate-spin" />
            Waking up the API server (free tier sleeps when idle). This takes up to a minute, only on the first visit.
          </div>
        )}
        <StatsBar stats={stats} />

        <div className="grid gap-6 lg:grid-cols-[240px_minmax(0,1fr)]">
          <FilterRail
            filters={filters}
            setFilters={setFilters}
            sectors={icp?.options.sectors ?? []}
            stages={icp?.options.stages ?? []}
          />

          <div className="min-w-0 overflow-hidden rounded-xl border border-border bg-surface">
            <div className="flex flex-wrap items-center gap-2 border-b border-border px-4 py-2.5">
              <nav className="flex gap-1 overflow-x-auto" aria-label="Lead status">
                {STATUS_TABS.map((t) => {
                  const active = JSON.stringify(t.value) === JSON.stringify(filters.status);
                  return (
                    <button
                      key={t.label}
                      onClick={() => setFilters({ ...filters, status: t.value })}
                      className={clsx(
                        "whitespace-nowrap rounded-md px-2.5 py-1.5 text-sm font-medium transition-colors",
                        active ? "bg-slate-900 text-white" : "text-muted hover:bg-slate-100 hover:text-foreground",
                      )}
                    >
                      {t.label}
                    </button>
                  );
                })}
              </nav>
              <div className="ml-auto flex items-center gap-2">
                <span className="text-xs text-muted tabular-nums">
                  {leads ? `${leads.total} leads` : ""}
                </span>
                <select
                  value={filters.sort}
                  onChange={(e) => setFilters({ ...filters, sort: e.target.value as Filters["sort"] })}
                  className="h-8 rounded-lg border border-border bg-surface px-2 text-xs outline-none focus:border-accent"
                  aria-label="Sort leads"
                >
                  {SORTS.map((s) => (
                    <option key={s.value} value={s.value}>
                      {s.label}
                    </option>
                  ))}
                </select>
                <Button size="sm" onClick={exportCsv} disabled={!items.length}>
                  <Download className="h-3.5 w-3.5" />
                  {checked.size ? `Export ${checked.size}` : "Export CSV"}
                </Button>
              </div>
            </div>

            {error ? (
              <div className="p-10 text-center text-sm text-rose-600">
                Can&apos;t reach the API at {API_URL}. Is the backend running?
              </div>
            ) : (
              <LeadTable
                leads={items}
                loading={isLoading && !leads}
                selectedId={openId}
                checked={checked}
                onToggleCheck={(id) =>
                  setChecked((s) => {
                    const n = new Set(s);
                    if (n.has(id)) n.delete(id);
                    else n.add(id);
                    return n;
                  })
                }
                onToggleAll={() =>
                  setChecked((s) => (items.every((l) => s.has(l.id)) ? new Set() : new Set(items.map((l) => l.id))))
                }
                onOpen={setOpenId}
                onStatus={setStatus}
                empty={noData ? <Onboarding /> : <NoMatches onClear={() => setFilters(DEFAULT_FILTERS)} />}
              />
            )}
          </div>
        </div>
      </main>

      {openId !== null && <LeadDrawer id={openId} onClose={() => setOpenId(null)} onChanged={refreshAll} />}
      {icpOpen && icp && (
        <IcpModal
          icp={icp.icp}
          options={icp.options}
          onClose={() => setIcpOpen(false)}
          onSaved={() => {
            mutateIcp();
            refreshAll();
          }}
        />
      )}
    </div>
  );
}

function Onboarding() {
  const steps = [
    { icon: Newspaper, title: "Watch funding news", body: "TechCrunch, PR Newswire, GeekWire and AlleyWatch, deduplicated." },
    { icon: Sparkles, title: "Extract & enrich", body: "AI pulls out the round, investors and people; we crawl the company site for contacts." },
    { icon: Target, title: "Rank by fit & timing", body: "Scored against your ideal customer, with the reasons shown." },
  ];
  return (
    <div className="px-6 py-14 text-center">
      <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-indigo-50 text-accent">
        <Radar className="h-6 w-6" />
      </div>
      <h2 className="text-lg font-semibold">No leads yet</h2>
      <p className="mx-auto mt-1 max-w-md text-sm text-muted">
        Click <span className="font-medium text-foreground">Find new leads</span> to pull this month&apos;s funding announcements. A first run takes about two minutes.
      </p>
      <div className="mx-auto mt-8 grid max-w-3xl gap-4 text-left sm:grid-cols-3">
        {steps.map((s, i) => (
          <div key={s.title} className="rounded-xl border border-border p-4">
            <s.icon className="mb-2 h-5 w-5 text-accent" />
            <div className="text-sm font-medium">
              {i + 1}. {s.title}
            </div>
            <div className="mt-1 text-xs text-muted">{s.body}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function NoMatches({ onClear }: { onClear: () => void }) {
  return (
    <div className="px-6 py-14 text-center">
      <p className="text-sm text-muted">No leads match these filters.</p>
      <Button size="sm" className="mt-3" onClick={onClear}>
        Clear filters
      </Button>
    </div>
  );
}
