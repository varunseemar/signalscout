"use client";

import clsx from "clsx";
import { Activity, Eye, Loader2, Play, Radar, SlidersHorizontal } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import useSWR from "swr";
import { useAccess } from "@/lib/access";
import { fetcher, send, type PipelineRun, type SourceHealth } from "@/lib/api";
import { Button } from "./ui";

const STAGES: Record<string, string> = {
  queued: "Starting…",
  crawling: "Crawling news sources…",
  extracting: "Extracting funding rounds with AI…",
  enriching: "Enriching company websites…",
  scoring: "Scoring leads…",
};

export function Header({ onOpenIcp, onRunFinished }: { onOpenIcp: () => void; onRunFinished: () => void }) {
  // Poll quickly only while a run is in progress
  const { data: runs, mutate } = useSWR<PipelineRun[]>("/api/pipeline/runs?limit=1", fetcher, {
    refreshInterval: (latest) => (latest?.[0]?.status === "running" ? 1500 : 0),
  });
  const run = runs?.[0];
  const running = run?.status === "running";
  const wasRunning = useRef(false);
  const { canEdit } = useAccess();

  useEffect(() => {
    if (wasRunning.current && !running) onRunFinished();
    wasRunning.current = running;
  }, [running, onRunFinished]);

  async function start() {
    try {
      await send("/api/pipeline/run", "POST");
    } catch {}
    mutate();
  }

  return (
    <header className="sticky top-0 z-20 border-b border-border bg-surface/90 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-[1500px] items-center gap-4 px-4 sm:px-6">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent text-white">
            <Radar className="h-4.5 w-4.5" />
          </div>
          <div className="leading-tight">
            <div className="text-[15px] font-semibold">SignalScout</div>
            <div className="hidden text-xs text-muted sm:block">Who to contact today, and why</div>
          </div>
        </div>

        <div className="ml-auto flex items-center gap-2">
          <SourceHealthIndicator />
          {run && (
            <span className="hidden text-xs text-muted md:inline">
              {running
                ? STAGES[run.stage ?? "queued"] ?? run.stage
                : run.status === "failed"
                  ? <span className="text-rose-600">Last run failed</span>
                  : `Updated ${new Date(run.finished_at ?? run.started_at).toLocaleString([], { dateStyle: "medium", timeStyle: "short" })}`}
            </span>
          )}
          {canEdit ? (
            <>
              <Button onClick={onOpenIcp}>
                <SlidersHorizontal className="h-4 w-4" />
                <span className="hidden sm:inline">Ideal customer</span>
              </Button>
              <Button variant="primary" onClick={start} disabled={running}>
                {running ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
                {running ? "Running" : "Find new leads"}
              </Button>
            </>
          ) : (
            <span
              title="Public demo: leads refresh automatically every 6 hours. Editing, re-scoring and manual runs are disabled."
              className="inline-flex items-center gap-1.5 rounded-full border border-border bg-slate-50 px-3 py-1.5 text-xs font-medium text-muted"
            >
              <Eye className="h-3.5 w-3.5" /> Read-only demo
            </span>
          )}
        </div>
      </div>
    </header>
  );
}

function SourceHealthIndicator() {
  const { data } = useSWR<SourceHealth[]>("/api/health/sources", fetcher, { refreshInterval: 30_000 });
  const [open, setOpen] = useState(false);
  if (!data?.length) return null;
  const worst = data.some((s) => s.status === "broken") ? "broken" : data.some((s) => s.status === "warning") ? "warning" : "ok";
  return (
    <div className="relative">
      <Button variant="ghost" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
        <Activity className="h-4 w-4" />
        <span className={clsx("h-2 w-2 rounded-full", dot(worst))} />
        <span className="hidden lg:inline">{data.length} sources</span>
      </Button>
      {open && (
        <div className="absolute right-0 top-11 w-80 rounded-xl border border-border bg-surface p-3 shadow-lg">
          <div className="mb-2 px-1 text-xs font-semibold uppercase tracking-wide text-muted">Scraper health</div>
          {data.map((s) => (
            <div key={s.source} className="flex items-start gap-2.5 rounded-lg px-1 py-2">
              <span className={clsx("mt-1.5 h-2 w-2 shrink-0 rounded-full", dot(s.status))} />
              <div className="min-w-0 flex-1">
                <div className="flex justify-between text-sm font-medium capitalize">
                  {s.source}
                  <span className="text-xs font-normal text-muted">
                    +{s.items_new} new · {s.items_skipped_seen} seen
                  </span>
                </div>
                {s.message && <div className="text-xs text-muted">{s.message}</div>}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

const dot = (s: string) => (s === "ok" ? "bg-emerald-500" : s === "warning" ? "bg-amber-500" : "bg-rose-500");
