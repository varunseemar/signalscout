"use client";

import { Loader2, X } from "lucide-react";
import { useState } from "react";
import { send, type Icp } from "@/lib/api";
import { Button, Chip } from "./ui";

export function IcpModal({
  icp,
  options,
  onClose,
  onSaved,
}: {
  icp: Icp;
  options: { sectors: string[]; stages: string[] };
  onClose: () => void;
  onSaved: () => void;
}) {
  const [form, setForm] = useState<Icp>(icp);
  const [saving, setSaving] = useState(false);
  const set = (patch: Partial<Icp>) => setForm({ ...form, ...patch });
  const toggle = (key: "sectors" | "stages", v: string) =>
    set({ [key]: form[key].includes(v) ? form[key].filter((x) => x !== v) : [...form[key], v] });

  async function save() {
    setSaving(true);
    try {
      await send("/api/icp", "PUT", form);
      onSaved();
      onClose();
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center p-4" role="dialog" aria-modal="true" aria-label="Ideal customer profile">
      <div className="absolute inset-0 bg-slate-900/30" onClick={onClose} />
      <div className="relative max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-2xl bg-surface shadow-2xl">
        <div className="flex items-start justify-between border-b border-border px-6 py-5">
          <div>
            <h2 className="text-lg font-semibold">Ideal customer profile</h2>
            <p className="text-sm text-muted">Leads are re-scored instantly when you save. No re-scraping needed.</p>
          </div>
          <button onClick={onClose} aria-label="Close" className="rounded-md p-1 text-muted hover:bg-slate-100">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="space-y-6 px-6 py-5">
          <Field label="What do you sell?" hint="Used to personalise AI-written emails">
            <textarea
              value={form.pitch}
              onChange={(e) => set({ pitch: e.target.value })}
              rows={2}
              className="w-full rounded-lg border border-border p-3 text-sm outline-none focus:border-accent focus:ring-2 focus:ring-indigo-100"
            />
          </Field>

          <Field label="Target sectors" hint="+20 points">
            <div className="flex flex-wrap gap-1.5">
              {options.sectors.map((s) => (
                <Chip key={s} active={form.sectors.includes(s)} onClick={() => toggle("sectors", s)}>
                  {s}
                </Chip>
              ))}
            </div>
          </Field>

          <Field label="Target stages" hint="+10 points">
            <div className="flex flex-wrap gap-1.5">
              {options.stages.map((s) => (
                <Chip key={s} active={form.stages.includes(s)} onClick={() => toggle("stages", s)}>
                  {s}
                </Chip>
              ))}
            </div>
          </Field>

          <Field label="Target countries" hint="Comma-separated, empty = anywhere (+10 points)">
            <input
              value={form.countries.join(", ")}
              onChange={(e) => set({ countries: e.target.value.split(",").map((s) => s.trim()).filter(Boolean) })}
              className="h-9 w-full rounded-lg border border-border px-3 text-sm outline-none focus:border-accent focus:ring-2 focus:ring-indigo-100"
            />
          </Field>

          <div className="grid gap-4 sm:grid-cols-3">
            <Field label="Min round ($M)">
              <NumberInput value={form.min_amount_usd / 1e6} onChange={(v) => set({ min_amount_usd: v * 1e6 })} />
            </Field>
            <Field label="Max round ($M)">
              <NumberInput value={form.max_amount_usd / 1e6} onChange={(v) => set({ max_amount_usd: v * 1e6 })} />
            </Field>
            <Field label="Signal fades after (days)">
              <NumberInput value={form.max_age_days} onChange={(v) => set({ max_age_days: Math.max(1, v) })} />
            </Field>
          </div>
        </div>

        <div className="flex justify-end gap-2 border-t border-border px-6 py-4">
          <Button onClick={onClose}>Cancel</Button>
          <Button variant="primary" onClick={save} disabled={saving}>
            {saving && <Loader2 className="h-4 w-4 animate-spin" />} Save & re-score
          </Button>
        </div>
      </div>
    </div>
  );
}

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <div className="mb-1.5 flex items-baseline justify-between">
        <span className="text-sm font-medium">{label}</span>
        {hint && <span className="text-xs text-muted">{hint}</span>}
      </div>
      {children}
    </label>
  );
}

function NumberInput({ value, onChange }: { value: number; onChange: (v: number) => void }) {
  return (
    <input
      type="number"
      min={0}
      value={Number.isFinite(value) ? value : 0}
      onChange={(e) => onChange(Number(e.target.value))}
      className="h-9 w-full rounded-lg border border-border px-3 text-sm tabular-nums outline-none focus:border-accent focus:ring-2 focus:ring-indigo-100"
    />
  );
}
