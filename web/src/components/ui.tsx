"use client";

import clsx from "clsx";
import { Check, Copy } from "lucide-react";
import { useState, type ButtonHTMLAttributes, type ReactNode } from "react";
import { scoreTone, type Email } from "@/lib/api";

export function Button({
  variant = "secondary",
  size = "md",
  className,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  size?: "sm" | "md";
}) {
  return (
    <button
      {...props}
      className={clsx(
        "inline-flex items-center justify-center gap-1.5 rounded-lg font-medium transition-colors",
        "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent",
        "disabled:cursor-not-allowed disabled:opacity-50",
        size === "sm" ? "h-8 px-2.5 text-xs" : "h-9 px-3.5 text-sm",
        variant === "primary" && "bg-accent text-white shadow-sm hover:bg-indigo-700",
        variant === "secondary" && "border border-border bg-surface text-foreground shadow-xs hover:bg-slate-50",
        variant === "ghost" && "text-muted hover:bg-slate-100 hover:text-foreground",
        variant === "danger" && "text-rose-600 hover:bg-rose-50",
        className,
      )}
    />
  );
}

export function ScoreBadge({ score, size = "md" }: { score: number; size?: "md" | "lg" }) {
  const tone = scoreTone(score);
  return (
    <div
      title={`Lead score ${score}/100`}
      className={clsx(
        "flex shrink-0 items-center justify-center rounded-full font-semibold tabular-nums ring-1 ring-inset",
        size === "lg" ? "h-14 w-14 text-xl" : "h-9 w-9 text-sm",
        tone === "hot" && "bg-emerald-50 text-hot ring-emerald-200",
        tone === "warm" && "bg-amber-50 text-warm ring-amber-200",
        tone === "cold" && "bg-slate-50 text-slate-500 ring-slate-200",
      )}
    >
      {score}
    </div>
  );
}

export function Chip({
  active,
  children,
  onClick,
}: {
  active?: boolean;
  children: ReactNode;
  onClick?: () => void;
}) {
  return (
    <button
      onClick={onClick}
      aria-pressed={active}
      className={clsx(
        "rounded-full border px-2.5 py-1 text-xs font-medium transition-colors",
        active
          ? "border-accent bg-indigo-50 text-accent"
          : "border-border bg-surface text-slate-600 hover:border-slate-300 hover:text-foreground",
      )}
    >
      {children}
    </button>
  );
}

export function Tag({ children, tone = "slate" }: { children: ReactNode; tone?: "slate" | "indigo" | "emerald" | "amber" | "rose" }) {
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[11px] font-medium",
        tone === "slate" && "bg-slate-100 text-slate-600",
        tone === "indigo" && "bg-indigo-50 text-indigo-700",
        tone === "emerald" && "bg-emerald-50 text-emerald-700",
        tone === "amber" && "bg-amber-50 text-amber-700",
        tone === "rose" && "bg-rose-50 text-rose-700",
      )}
    >
      {children}
    </span>
  );
}

const CONFIDENCE = {
  high: { tone: "emerald", label: "Verified", hint: "On company domain and the domain accepts mail (MX)" },
  medium: { tone: "amber", label: "Deliverable", hint: "Domain accepts mail, but it's not the company domain" },
  low: { tone: "rose", label: "Risky", hint: "No MX record - likely to bounce" },
} as const;

export function ConfidenceTag({ email }: { email: Email }) {
  const c = CONFIDENCE[email.confidence];
  return (
    <span title={c.hint}>
      <Tag tone={c.tone}>{c.label}</Tag>
    </span>
  );
}

export function CopyButton({ text, label }: { text: string; label?: string }) {
  const [done, setDone] = useState(false);
  return (
    <button
      onClick={(e) => {
        e.stopPropagation();
        navigator.clipboard.writeText(text);
        setDone(true);
        setTimeout(() => setDone(false), 1200);
      }}
      className="inline-flex items-center gap-1 rounded-md p-1 text-xs text-muted hover:bg-slate-100 hover:text-foreground"
      title="Copy"
      aria-label={label ?? "Copy"}
    >
      {done ? <Check className="h-3.5 w-3.5 text-hot" /> : <Copy className="h-3.5 w-3.5" />}
      {label}
    </button>
  );
}

export function Section({ title, children, action }: { title: string; children: ReactNode; action?: ReactNode }) {
  return (
    <section className="border-t border-border px-6 py-5">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-muted">{title}</h3>
        {action}
      </div>
      {children}
    </section>
  );
}

export function LinkedinIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className={className} aria-hidden="true">
      <path d="M20.45 20.45h-3.56v-5.57c0-1.33-.02-3.04-1.85-3.04-1.85 0-2.14 1.45-2.14 2.94v5.67H9.35V9h3.41v1.56h.05c.48-.9 1.64-1.85 3.37-1.85 3.6 0 4.27 2.37 4.27 5.46v6.28zM5.34 7.43a2.06 2.06 0 1 1 0-4.13 2.06 2.06 0 0 1 0 4.13zM7.12 20.45H3.56V9h3.56v11.45zM22.22 0H1.77C.79 0 0 .77 0 1.73v20.54C0 23.23.79 24 1.77 24h20.45c.98 0 1.78-.77 1.78-1.73V1.73C24 .77 23.2 0 22.22 0z" />
    </svg>
  );
}
