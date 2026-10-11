"use client";

import { Search, X } from "lucide-react";
import type { Filters, LeadStatus } from "@/lib/api";
import { Chip } from "./ui";

const RECENCY = [
  { label: "7 days", value: 7 },
  { label: "14 days", value: 14 },
  { label: "30 days", value: 30 },
  { label: "Any", value: null },
];

export const DEFAULT_FILTERS: Filters = {
  q: "",
  sector: [],
  stage: [],
  status: [],
  min_score: 0,
  days: null,
  has_email: false,
  sort: "score",
};

function toggle<T>(list: T[], v: T): T[] {
  return list.includes(v) ? list.filter((x) => x !== v) : [...list, v];
}

export function FilterRail({
  filters,
  setFilters,
  sectors,
  stages,
}: {
  filters: Filters;
  setFilters: (f: Filters) => void;
  sectors: string[];
  stages: string[];
}) {
  const set = (patch: Partial<Filters>) => setFilters({ ...filters, ...patch });
  const dirty = JSON.stringify(filters) !== JSON.stringify(DEFAULT_FILTERS);

  return (
    <aside className="space-y-6">
      <div className="relative">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
        <input
          value={filters.q}
          onChange={(e) => set({ q: e.target.value })}
          placeholder="Search companies…"
          className="h-9 w-full rounded-lg border border-border bg-surface pl-9 pr-3 text-sm outline-none placeholder:text-slate-400 focus:border-accent focus:ring-2 focus:ring-indigo-100"
        />
      </div>

      <Group title="Minimum score" right={<span className="tabular-nums text-foreground">{filters.min_score}</span>}>
        <input
          type="range"
          min={0}
          max={90}
          step={5}
          value={filters.min_score}
          onChange={(e) => set({ min_score: Number(e.target.value) })}
          className="w-full accent-[var(--accent)]"
          aria-label="Minimum score"
        />
      </Group>

      <Group title="Raised within">
        <div className="flex flex-wrap gap-1.5">
          {RECENCY.map((r) => (
            <Chip key={r.label} active={filters.days === r.value} onClick={() => set({ days: r.value })}>
              {r.label}
            </Chip>
          ))}
        </div>
      </Group>

      <Group title="Stage">
        <div className="flex flex-wrap gap-1.5">
          {stages.map((s) => (
            <Chip key={s} active={filters.stage.includes(s)} onClick={() => set({ stage: toggle(filters.stage, s) })}>
              {s}
            </Chip>
          ))}
        </div>
      </Group>

      <Group title="Sector">
        <div className="flex flex-wrap gap-1.5">
          {sectors.map((s) => (
            <Chip key={s} active={filters.sector.includes(s)} onClick={() => set({ sector: toggle(filters.sector, s) })}>
              {s}
            </Chip>
          ))}
        </div>
      </Group>

      <Group title="Contactability">
        <label className="flex cursor-pointer items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={filters.has_email}
            onChange={(e) => set({ has_email: e.target.checked })}
            className="h-4 w-4 rounded accent-[var(--accent)]"
          />
          Has an email address
        </label>
      </Group>

      {dirty && (
        <button
          onClick={() => setFilters({ ...DEFAULT_FILTERS, status: filters.status })}
          className="inline-flex items-center gap-1 text-xs font-medium text-muted hover:text-foreground"
        >
          <X className="h-3.5 w-3.5" /> Clear filters
        </button>
      )}
    </aside>
  );
}

function Group({ title, right, children }: { title: string; right?: React.ReactNode; children: React.ReactNode }) {
  return (
    <div>
      <div className="mb-2 flex justify-between text-xs font-semibold uppercase tracking-wide text-muted">
        {title}
        {right}
      </div>
      {children}
    </div>
  );
}

export const STATUS_TABS: { label: string; value: LeadStatus[] }[] = [
  { label: "All active", value: [] },
  { label: "New", value: ["new"] },
  { label: "Shortlisted", value: ["shortlisted"] },
  { label: "Contacted", value: ["contacted"] },
  { label: "Dismissed", value: ["dismissed"] },
];
