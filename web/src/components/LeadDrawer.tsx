"use client";

import clsx from "clsx";
import {
  Briefcase,
  CheckCircle2,
  ExternalLink,
  Globe,

  Loader2,
  Mail,
  Newspaper,
  Phone,
  RefreshCw,
  Sparkles,
  Star,
  X,
} from "lucide-react";
import { useEffect, useState } from "react";
import useSWR from "swr";
import { daysAgo, fetcher, money, send, type EmailDraft, type LeadDetail, type LeadStatus } from "@/lib/api";
import { Button, ConfidenceTag, CopyButton, LinkedinIcon, ScoreBadge, Section, Tag } from "./ui";

const BREAKDOWN = [
  { key: "fit", label: "ICP fit", max: 40 },
  { key: "timing", label: "Timing", max: 25 },
  { key: "size", label: "Deal size", max: 15 },
  { key: "reachability", label: "Reachability", max: 20 },
] as const;

export function LeadDrawer({
  id,
  onClose,
  onChanged,
}: {
  id: number;
  onClose: () => void;
  onChanged: () => void;
}) {
  const { data: lead, mutate } = useSWR<LeadDetail>(`/api/leads/${id}`, fetcher);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  async function setStatus(status: LeadStatus) {
    await send(`/api/leads/${id}`, "PATCH", { status });
    mutate();
    onChanged();
  }

  return (
    <div className="fixed inset-0 z-30 flex justify-end" role="dialog" aria-modal="true" aria-label="Lead details">
      <div className="absolute inset-0 bg-slate-900/20" onClick={onClose} />
      <div className="animate-slide-in relative flex h-full w-full max-w-xl flex-col overflow-y-auto bg-surface shadow-2xl">
        {!lead ? (
          <div className="flex flex-1 items-center justify-center text-muted">
            <Loader2 className="h-5 w-5 animate-spin" />
          </div>
        ) : (
          <>
            <div className="sticky top-0 z-10 border-b border-border bg-surface px-6 py-5">
              <div className="flex items-start gap-4">
                <ScoreBadge score={lead.score} size="lg" />
                <div className="min-w-0 flex-1">
                  <h2 className="truncate text-lg font-semibold">{lead.name}</h2>
                  <p className="line-clamp-2 text-sm text-muted">{lead.description}</p>
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {lead.sector && <Tag tone="indigo">{lead.sector}</Tag>}
                    {(lead.hq_city || lead.hq_country) && (
                      <Tag>{[lead.hq_city, lead.hq_country].filter(Boolean).join(", ")}</Tag>
                    )}
                    {lead.hiring && (
                      <Tag tone="emerald">
                        <Briefcase className="h-3 w-3" /> Hiring
                      </Tag>
                    )}
                  </div>
                </div>
                <button onClick={onClose} aria-label="Close" className="rounded-md p-1 text-muted hover:bg-slate-100">
                  <X className="h-5 w-5" />
                </button>
              </div>
              <div className="mt-4 flex gap-2">
                <Button
                  size="sm"
                  variant={lead.status === "shortlisted" ? "primary" : "secondary"}
                  onClick={() => setStatus(lead.status === "shortlisted" ? "new" : "shortlisted")}
                >
                  <Star className="h-3.5 w-3.5" /> {lead.status === "shortlisted" ? "Shortlisted" : "Shortlist"}
                </Button>
                <Button
                  size="sm"
                  variant={lead.status === "contacted" ? "primary" : "secondary"}
                  onClick={() => setStatus(lead.status === "contacted" ? "new" : "contacted")}
                >
                  <CheckCircle2 className="h-3.5 w-3.5" /> {lead.status === "contacted" ? "Contacted" : "Mark contacted"}
                </Button>
                <Button size="sm" variant="danger" className="ml-auto" onClick={() => setStatus(lead.status === "dismissed" ? "new" : "dismissed")}>
                  {lead.status === "dismissed" ? "Restore" : "Not a fit"}
                </Button>
              </div>
            </div>

            <Section title="Why this lead">
              <ul className="mb-4 space-y-1.5">
                {lead.score_reasons.map((r) => (
                  <li key={r} className="flex gap-2 text-sm">
                    <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />
                    {r}
                  </li>
                ))}
              </ul>
              <div className="grid grid-cols-2 gap-x-6 gap-y-2.5">
                {BREAKDOWN.map((b) => {
                  const v = lead.score_breakdown?.[b.key] ?? 0;
                  return (
                    <div key={b.key}>
                      <div className="mb-1 flex justify-between text-xs">
                        <span className="text-muted">{b.label}</span>
                        <span className="tabular-nums">
                          {v}/{b.max}
                        </span>
                      </div>
                      <div className="h-1.5 overflow-hidden rounded-full bg-slate-100">
                        <div className="h-full rounded-full bg-accent" style={{ width: `${(v / b.max) * 100}%` }} />
                      </div>
                    </div>
                  );
                })}
              </div>
            </Section>

            {lead.funding_events.map((e) => (
              <Section
                key={e.id}
                title="Funding signal"
                action={<span className="text-xs text-muted">{e.announced_on} · {daysAgo(e.announced_on)}</span>}
              >
                <div className="flex items-baseline gap-2">
                  <span className="text-2xl font-semibold tabular-nums">{money(e.amount_usd)}</span>
                  <span className="text-sm text-muted">{e.round_type}</span>
                  {e.valuation_usd && <span className="text-sm text-muted">· {money(e.valuation_usd)} valuation</span>}
                </div>
                {e.summary && <p className="mt-2 text-sm text-slate-700">{e.summary}</p>}
                <dl className="mt-3 grid grid-cols-[110px_1fr] gap-y-1.5 text-sm">
                  {e.use_of_funds && (
                    <>
                      <dt className="text-muted">Use of funds</dt>
                      <dd>{e.use_of_funds}</dd>
                    </>
                  )}
                  {e.lead_investors.length > 0 && (
                    <>
                      <dt className="text-muted">Led by</dt>
                      <dd>{e.lead_investors.join(", ")}</dd>
                    </>
                  )}
                  {e.investors.length > e.lead_investors.length && (
                    <>
                      <dt className="text-muted">Investors</dt>
                      <dd className="text-slate-700">{e.investors.join(", ")}</dd>
                    </>
                  )}
                  {e.source_count > 1 && (
                    <>
                      <dt className="text-muted">Coverage</dt>
                      <dd>Reported by {e.source_count} outlets (merged)</dd>
                    </>
                  )}
                </dl>
              </Section>
            ))}

            <Section
              title="Contact"
              action={<span className="text-xs text-muted">Data quality {lead.data_quality}/100</span>}
            >
              <div className="space-y-2 text-sm">
                {lead.website && (
                  <Row icon={<Globe className="h-4 w-4" />}>
                    <a href={lead.website} target="_blank" rel="noreferrer" className="text-accent hover:underline">
                      {lead.domain ?? lead.website}
                    </a>
                    {lead.website_source === "guessed" && <Tag tone="amber">matched by name</Tag>}
                  </Row>
                )}
                {lead.emails.map((em) => (
                  <Row key={em.email} icon={<Mail className="h-4 w-4" />}>
                    <span className="font-mono text-[13px]">{em.email}</span>
                    <ConfidenceTag email={em} />
                    {em.type === "role" && <Tag>role inbox</Tag>}
                    <CopyButton text={em.email} />
                  </Row>
                ))}
                {lead.phones.map((p) => (
                  <Row key={p.e164} icon={<Phone className="h-4 w-4" />}>
                    <a href={`tel:${p.e164}`} className="font-mono text-[13px] hover:underline">
                      {p.display}
                    </a>
                    <CopyButton text={p.e164} />
                  </Row>
                ))}
                {lead.socials.linkedin && (
                  <Row icon={<LinkedinIcon className="h-4 w-4" />}>
                    <a href={lead.socials.linkedin} target="_blank" rel="noreferrer" className="text-accent hover:underline">
                      Company page
                    </a>
                  </Row>
                )}
                {!lead.emails.length && !lead.phones.length && (
                  <p className="text-sm text-muted">
                    {lead.enrich_status === "no_website"
                      ? "No website found for this company yet."
                      : lead.enrich_status === "unreachable"
                        ? "Website couldn't be reached (or robots.txt disallows it)."
                        : "No public email or phone on the company website."}{" "}
                    Try the people below.
                  </p>
                )}
              </div>

              {lead.people.length > 0 && (
                <div className="mt-4">
                  <div className="mb-1.5 text-xs font-medium text-muted">People mentioned in coverage</div>
                  <div className="divide-y divide-border rounded-lg border border-border">
                    {lead.people.map((p) => (
                      <div key={p.name} className="flex items-center justify-between px-3 py-2">
                        <div>
                          <div className="text-sm font-medium">{p.name}</div>
                          <div className="text-xs text-muted">{p.title ?? "—"}</div>
                        </div>
                        <a
                          href={`https://www.linkedin.com/search/results/people/?keywords=${encodeURIComponent(`${p.name} ${lead.name}`)}`}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex items-center gap-1 text-xs text-accent hover:underline"
                        >
                          Find on LinkedIn <ExternalLink className="h-3 w-3" />
                        </a>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </Section>

            <OutreachDraft lead={lead} onUpdated={() => mutate()} />

            <Section title="Sources">
              <ul className="space-y-2">
                {lead.articles.map((a) => (
                  <li key={a.id}>
                    <a href={a.url} target="_blank" rel="noreferrer" className="group flex gap-2 text-sm">
                      <Newspaper className="mt-0.5 h-4 w-4 shrink-0 text-muted" />
                      <span>
                        <span className="group-hover:underline">{a.title}</span>
                        <span className="block text-xs capitalize text-muted">
                          {a.source} · {a.published_at}
                        </span>
                      </span>
                    </a>
                  </li>
                ))}
              </ul>
            </Section>

            <Notes id={lead.id} initial={lead.notes ?? ""} />
          </>
        )}
      </div>
    </div>
  );
}

function Row({ icon, children }: { icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-2.5">
      <span className="text-muted">{icon}</span>
      <div className="flex min-w-0 flex-wrap items-center gap-2">{children}</div>
    </div>
  );
}

function OutreachDraft({ lead, onUpdated }: { lead: LeadDetail; onUpdated: () => void }) {
  const [draft, setDraft] = useState<EmailDraft | null>(lead.email_draft);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function generate(regenerate = false) {
    setLoading(true);
    setError(null);
    try {
      const d = await send<EmailDraft>(`/api/leads/${lead.id}/email-draft?regenerate=${regenerate}`, "POST");
      setDraft(d);
      onUpdated();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to generate");
    } finally {
      setLoading(false);
    }
  }

  const to = lead.emails.find((e) => e.type === "personal" && e.confidence !== "low") ?? lead.emails[0];

  return (
    <Section
      title="First-touch email"
      action={
        draft && (
          <Button size="sm" variant="ghost" onClick={() => generate(true)} disabled={loading}>
            <RefreshCw className={clsx("h-3.5 w-3.5", loading && "animate-spin")} /> Regenerate
          </Button>
        )
      }
    >
      {!draft ? (
        <div className="rounded-lg border border-dashed border-border p-4 text-center">
          <p className="mb-3 text-sm text-muted">Draft a short email that references this round and your offer.</p>
          <Button variant="primary" size="sm" onClick={() => generate()} disabled={loading}>
            {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}
            Write email with AI
          </Button>
          {error && <p className="mt-2 text-xs text-rose-600">{error}</p>}
        </div>
      ) : (
        <div className="rounded-lg border border-border">
          <div className="border-b border-border px-3 py-2 text-sm">
            <span className="text-muted">Subject: </span>
            <span className="font-medium">{draft.subject}</span>
          </div>
          <pre className="whitespace-pre-wrap px-3 py-3 font-sans text-sm leading-relaxed text-slate-700">{draft.body}</pre>
          <div className="flex items-center justify-between gap-2 border-t border-border bg-slate-50 px-3 py-2">
            <span className="text-xs text-muted">{draft.contact_hint}</span>
            <div className="flex shrink-0 gap-1">
              <CopyButton text={`Subject: ${draft.subject}\n\n${draft.body}`} label="Copy" />
              <a
                href={`mailto:${to?.email ?? ""}?subject=${encodeURIComponent(draft.subject)}&body=${encodeURIComponent(draft.body)}`}
                className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-accent hover:bg-indigo-50"
              >
                <Mail className="h-3.5 w-3.5" /> Open in mail
              </a>
            </div>
          </div>
        </div>
      )}
    </Section>
  );
}

function Notes({ id, initial }: { id: number; initial: string }) {
  const [value, setValue] = useState(initial);
  const [saved, setSaved] = useState(true);
  return (
    <Section title="Notes" action={!saved && <span className="text-xs text-muted">Saving…</span>}>
      <textarea
        value={value}
        onChange={(e) => {
          setValue(e.target.value);
          setSaved(false);
        }}
        onBlur={async () => {
          await send(`/api/leads/${id}`, "PATCH", { notes: value });
          setSaved(true);
        }}
        rows={3}
        placeholder="Add context for your team…"
        className="w-full resize-none rounded-lg border border-border p-3 text-sm outline-none focus:border-accent focus:ring-2 focus:ring-indigo-100"
      />
    </Section>
  );
}
