export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type Email = {
  email: string;
  type: "role" | "personal";
  mx_valid: boolean;
  same_domain: boolean;
  confidence: "high" | "medium" | "low";
};
export type Phone = { e164: string; display: string; region: string };
export type Person = { name: string; title?: string | null; source?: string };

export type Round = {
  id: number;
  round_type: string | null;
  amount_usd: number | null;
  valuation_usd: number | null;
  investors: string[];
  lead_investors: string[];
  use_of_funds: string | null;
  summary: string | null;
  announced_on: string | null;
  source_count: number;
};

export type LeadStatus = "new" | "shortlisted" | "contacted" | "dismissed";

export type Lead = {
  id: number;
  name: string;
  domain: string | null;
  website: string | null;
  description: string | null;
  sector: string | null;
  hq_city: string | null;
  hq_country: string | null;
  score: number;
  score_breakdown: { fit: number; timing: number; size: number; reachability: number };
  score_reasons: string[];
  data_quality: number;
  status: LeadStatus;
  hiring: boolean | null;
  enrich_status: string;
  best_email: Email | null;
  email_count: number;
  phone: string | null;
  linkedin: string | null;
  latest_round: Round | null;
};

export type EmailDraft = { subject: string; body: string; contact_hint: string };

export type LeadDetail = Lead & {
  emails: Email[];
  phones: Phone[];
  socials: Record<string, string>;
  people: Person[];
  website_source: string | null;
  site_title: string | null;
  meta_description: string | null;
  notes: string | null;
  email_draft: EmailDraft | null;
  enriched_at: string | null;
  funding_events: Round[];
  articles: { id: number; title: string; url: string; source: string; published_at: string | null }[];
};

export type Stats = {
  articles: number;
  funding_articles: number;
  filtered_out: number;
  leads: number;
  hot_leads: number;
  with_verified_email: number;
  raised_this_week_usd: number;
  merged_duplicates: number;
};

export type Icp = {
  pitch: string;
  sectors: string[];
  countries: string[];
  stages: string[];
  min_amount_usd: number;
  max_amount_usd: number;
  max_age_days: number;
};

export type PipelineRun = {
  id: number;
  status: "running" | "finished" | "failed";
  stage: string | null;
  started_at: string;
  finished_at: string | null;
  stats: Record<string, number>;
  error: string | null;
};

export type SourceHealth = {
  source: string;
  status: "ok" | "warning" | "broken";
  message: string | null;
  feed_entries: number;
  items_new: number;
  items_skipped_seen: number;
  items_dropped: number;
  checked_at: string;
};

export type Filters = {
  q: string;
  sector: string[];
  stage: string[];
  status: LeadStatus[];
  min_score: number;
  days: number | null;
  has_email: boolean;
  sort: "score" | "recent" | "amount" | "name";
};

export function toQuery(f: Partial<Filters> & { ids?: number[] }): string {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(f)) {
    if (v === null || v === undefined || v === "" || v === false || v === 0) continue;
    if (Array.isArray(v)) v.forEach((x) => p.append(k, String(x)));
    else p.set(k, String(v));
  }
  return p.toString();
}

export async function fetcher<T>(path: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`);
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json();
}

export async function send<T>(path: string, method: string, body?: unknown): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    let msg = res.statusText;
    try {
      msg = (await res.json()).detail ?? msg;
    } catch {}
    throw new Error(msg);
  }
  return res.json();
}

// ---------- formatting ----------

export function money(v: number | null | undefined): string {
  if (!v) return "—";
  if (v >= 1e9) return `$${(v / 1e9).toFixed(1)}B`;
  if (v >= 1e6) return `$${(v / 1e6).toFixed(v >= 1e7 ? 0 : 1)}M`;
  return `$${Math.round(v / 1e3)}K`;
}

export function daysAgo(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = Math.floor((Date.now() - new Date(iso + "T00:00:00").getTime()) / 86_400_000);
  if (d <= 0) return "today";
  if (d === 1) return "yesterday";
  return `${d}d ago`;
}

export function scoreTone(score: number): "hot" | "warm" | "cold" {
  return score >= 80 ? "hot" : score >= 60 ? "warm" : "cold";
}
