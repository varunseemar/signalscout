"use client";

import { money, type Stats } from "@/lib/api";

export function StatsBar({ stats }: { stats?: Stats }) {
  const items = [
    { label: "Hot leads", value: stats?.hot_leads, hint: "Score 80+", accent: true },
    { label: "Active leads", value: stats?.leads },
    { label: "Verified emails", value: stats?.with_verified_email, hint: "On company domain + MX" },
    { label: "Raised this week", value: stats ? money(stats.raised_this_week_usd) : undefined },
    {
      label: "Noise filtered",
      value: stats?.filtered_out,
      hint: stats ? `of ${stats.articles} articles weren't company raises` : undefined,
    },
    { label: "Duplicates merged", value: stats?.merged_duplicates, hint: "Same round, multiple outlets" },
  ];
  return (
    <div className="grid grid-cols-2 gap-px overflow-hidden rounded-xl border border-border bg-border sm:grid-cols-3 xl:grid-cols-6">
      {items.map((i) => (
        <div key={i.label} className="bg-surface px-4 py-3">
          <div className="text-xs text-muted">{i.label}</div>
          <div className={`mt-0.5 text-2xl font-semibold tabular-nums ${i.accent ? "text-hot" : ""}`}>
            {i.value ?? <span className="inline-block h-6 w-10 animate-pulse rounded bg-slate-100" />}
          </div>
          {i.hint && <div className="truncate text-[11px] text-muted">{i.hint}</div>}
        </div>
      ))}
    </div>
  );
}
