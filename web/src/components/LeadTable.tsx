"use client";

import clsx from "clsx";
import { Briefcase, Mail, Phone, Star, X } from "lucide-react";
import { daysAgo, money, type Lead, type LeadStatus } from "@/lib/api";
import { LinkedinIcon, ScoreBadge, Tag } from "./ui";

export function LeadTable({
  leads,
  loading,
  selectedId,
  checked,
  onToggleCheck,
  onToggleAll,
  onOpen,
  onStatus,
  empty,
}: {
  leads: Lead[];
  loading: boolean;
  selectedId: number | null;
  checked: Set<number>;
  onToggleCheck: (id: number) => void;
  onToggleAll: () => void;
  onOpen: (id: number) => void;
  onStatus: (id: number, s: LeadStatus) => void;
  empty: React.ReactNode;
}) {
  if (loading) {
    return (
      <div className="divide-y divide-border">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="flex items-center gap-4 px-4 py-4">
            <div className="h-9 w-9 animate-pulse rounded-full bg-slate-100" />
            <div className="flex-1 space-y-2">
              <div className="h-3.5 w-1/3 animate-pulse rounded bg-slate-100" />
              <div className="h-3 w-2/3 animate-pulse rounded bg-slate-100" />
            </div>
          </div>
        ))}
      </div>
    );
  }
  if (!leads.length) return <>{empty}</>;

  const allChecked = leads.every((l) => checked.has(l.id));
  return (
    <div role="table" aria-label="Leads">
      <div
        role="row"
        className="hidden grid-cols-[28px_44px_minmax(0,2.4fr)_minmax(0,1.3fr)_minmax(0,2fr)_96px_76px] items-center gap-3 border-b border-border px-4 py-2 text-[11px] font-semibold uppercase tracking-wide text-muted lg:grid"
      >
        <input type="checkbox" checked={allChecked} onChange={onToggleAll} aria-label="Select all" className="h-4 w-4 accent-[var(--accent)]" />
        <span>Score</span>
        <span>Company</span>
        <span>Signal</span>
        <span>Why now</span>
        <span>Reach</span>
        <span />
      </div>
      <ul className="divide-y divide-border">
        {leads.map((l) => {
          const r = l.latest_round;
          return (
            <li
              key={l.id}
              role="row"
              onClick={() => onOpen(l.id)}
              className={clsx(
                "group grid cursor-pointer grid-cols-[28px_44px_minmax(0,1fr)] items-center gap-3 px-4 py-3.5 transition-colors lg:grid-cols-[28px_44px_minmax(0,2.4fr)_minmax(0,1.3fr)_minmax(0,2fr)_96px_76px]",
                selectedId === l.id ? "bg-indigo-50/60" : "hover:bg-slate-50",
              )}
            >
              <input
                type="checkbox"
                checked={checked.has(l.id)}
                onClick={(e) => e.stopPropagation()}
                onChange={() => onToggleCheck(l.id)}
                aria-label={`Select ${l.name}`}
                className="h-4 w-4 accent-[var(--accent)]"
              />
              <ScoreBadge score={l.score} />

              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className="truncate font-medium">{l.name}</span>
                  {l.status === "shortlisted" && <Star className="h-3.5 w-3.5 shrink-0 fill-amber-400 text-amber-400" />}
                  {l.status === "contacted" && <Tag tone="indigo">Contacted</Tag>}
                </div>
                <div className="truncate text-xs text-muted">
                  {l.domain ?? "no website"} · {l.sector ?? "—"}
                  {l.hq_city ? ` · ${l.hq_city}` : ""}
                </div>
                {/* compact signal for small screens */}
                <div className="mt-1 text-xs text-slate-600 lg:hidden">
                  {r?.round_type} {money(r?.amount_usd)} · {daysAgo(r?.announced_on)}
                </div>
              </div>

              <div className="hidden min-w-0 lg:block">
                <div className="text-sm font-semibold tabular-nums">{money(r?.amount_usd)}</div>
                <div className="text-xs text-muted">
                  {r?.round_type ?? "—"} · {daysAgo(r?.announced_on)}
                </div>
              </div>

              <div className="hidden min-w-0 text-xs text-slate-600 lg:block">
                <p className="line-clamp-2">{r?.summary ?? l.description}</p>
              </div>

              <div className="hidden items-center gap-1.5 lg:flex">
                <ReachIcon on={!!l.best_email} good={l.best_email?.confidence === "high"} label={l.best_email ? `${l.best_email.email} (${l.best_email.confidence})` : "No email"}>
                  <Mail className="h-3.5 w-3.5" />
                </ReachIcon>
                <ReachIcon on={!!l.phone} good label={l.phone ?? "No phone"}>
                  <Phone className="h-3.5 w-3.5" />
                </ReachIcon>
                <ReachIcon on={!!l.linkedin} good label={l.linkedin ? "LinkedIn page" : "No LinkedIn"}>
                  <LinkedinIcon className="h-3.5 w-3.5" />
                </ReachIcon>
                {l.hiring && (
                  <ReachIcon on good label="Hiring">
                    <Briefcase className="h-3.5 w-3.5" />
                  </ReachIcon>
                )}
              </div>

              <div className="hidden justify-end gap-0.5 opacity-0 transition-opacity group-hover:opacity-100 lg:flex">
                <IconAction
                  label={l.status === "shortlisted" ? "Remove from shortlist" : "Shortlist"}
                  onClick={() => onStatus(l.id, l.status === "shortlisted" ? "new" : "shortlisted")}
                >
                  <Star className={clsx("h-4 w-4", l.status === "shortlisted" && "fill-amber-400 text-amber-400")} />
                </IconAction>
                <IconAction label="Dismiss" onClick={() => onStatus(l.id, l.status === "dismissed" ? "new" : "dismissed")}>
                  <X className="h-4 w-4" />
                </IconAction>
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function ReachIcon({ on, good, label, children }: { on: boolean; good?: boolean; label: string; children: React.ReactNode }) {
  return (
    <span
      title={label}
      aria-label={label}
      className={clsx(
        "flex h-6 w-6 items-center justify-center rounded-md",
        !on && "text-slate-300",
        on && good && "bg-emerald-50 text-emerald-600",
        on && !good && "bg-amber-50 text-amber-600",
      )}
    >
      {children}
    </span>
  );
}

function IconAction({ label, onClick, children }: { label: string; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      title={label}
      aria-label={label}
      onClick={(e) => {
        e.stopPropagation();
        onClick();
      }}
      className="rounded-md p-1.5 text-muted hover:bg-white hover:text-foreground hover:shadow-sm"
    >
      {children}
    </button>
  );
}
