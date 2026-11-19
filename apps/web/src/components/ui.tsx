/**
 * UI primitives, in the style of the reference mock-up (rounded panels, pastel key figures,
 * pill buttons, dark highlight card). Design rules applied everywhere:
 *  1. One primary action per screen (filled button); everything else is secondary.
 *  2. Status is always words + colour, never colour alone (accessibility).
 *  3. Progressive disclosure: technical detail lives in <Disclosure>, closed by default.
 *  4. Every empty state says what to do next.
 */
import { ChevronDown } from "lucide-react";
import type { ButtonHTMLAttributes, HTMLAttributes, ReactNode } from "react";
import { useState } from "react";
import { cn } from "@/lib/utils";
import { InfoTip } from "./InfoTip";
import { InTitleSlot } from "./shell/TitleSlot";

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger" | "light";

const buttonStyles: Record<ButtonVariant, string> = {
  primary: "bg-accent text-white shadow-soft hover:bg-accent/90",
  secondary: "bg-white text-ink border border-line hover:bg-surface",
  ghost: "text-muted hover:bg-surface hover:text-ink",
  danger: "bg-white text-urgent border border-urgent/30 hover:bg-urgent-soft",
  light: "bg-p-sky text-rail hover:bg-white", // on dark cards
};

export function Button({
  variant = "primary",
  size = "md",
  className,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  size?: "sm" | "md" | "lg";
}) {
  return (
    <button
      type="button"
      className={cn(
        "inline-flex items-center justify-center gap-1.5 rounded-full font-semibold transition-colors",
        "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent",
        "disabled:cursor-not-allowed disabled:opacity-50",
        { sm: "h-8 px-3 text-xs", md: "h-10 px-4 text-sm", lg: "h-12 px-6 text-[15px]" }[size],
        buttonStyles[variant],
        className,
      )}
      {...props}
    />
  );
}

export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("rounded-3xl border border-line bg-white", className)} {...props} />;
}

/** Card title. An optional `hint` is available on demand behind (i), never as a second line. */
export function CardHeader({
  title,
  hint,
  children,
}: {
  title: ReactNode;
  hint?: string;
  children?: ReactNode;
}) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-line px-6 py-4">
      <h2 className="flex items-center gap-1.5 text-base font-bold">
        {title}
        {hint && <InfoTip text={hint} />}
      </h2>
      {children}
    </div>
  );
}

/** Page title (in the shell's top bar) + the page's primary action, nothing else. */
export function PageHeader({ title, action }: { title: string; action?: ReactNode }) {
  return (
    <>
      <InTitleSlot>
        <h1 className="truncate text-[28px] font-extrabold tracking-tight">{title}</h1>
      </InTitleSlot>
      {action && <div className="mb-6 flex flex-wrap items-center justify-end gap-3">{action}</div>}
    </>
  );
}

export type Tone = "neutral" | "accent" | "urgent" | "high" | "ok";
const toneStyles: Record<Tone, string> = {
  neutral: "bg-surface text-muted border-line",
  accent: "bg-accent-soft text-accent border-accent/20",
  urgent: "bg-urgent-soft text-urgent border-urgent/20",
  high: "bg-high-soft text-high border-high/20",
  ok: "bg-ok-soft text-ok border-ok/20",
};

export function Badge({
  tone = "neutral",
  className,
  ...props
}: HTMLAttributes<HTMLSpanElement> & { tone?: Tone }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 whitespace-nowrap rounded-full border px-2.5 py-0.5 text-xs font-semibold",
        toneStyles[tone],
        className,
      )}
      {...props}
    />
  );
}

export function Notice({
  tone = "accent",
  icon,
  children,
}: {
  tone?: Tone;
  icon?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className={cn("flex items-start gap-2 rounded-2xl border px-4 py-3 text-sm", toneStyles[tone])}>
      {icon && <span className="mt-0.5 shrink-0">{icon}</span>}
      <div>{children}</div>
    </div>
  );
}

export type Pastel = "lavender" | "mint" | "cream" | "sky" | "rose";
const pastelStyles: Record<Pastel, string> = {
  lavender: "bg-p-lavender",
  mint: "bg-p-mint",
  cream: "bg-p-cream",
  sky: "bg-p-sky",
  rose: "bg-p-rose",
};

/**
 * A number that answers one question. Pastel background for the key figures of a screen;
 * `tone` turns it into an alert when the number needs attention.
 */
export function Kpi({
  label,
  value,
  hint,
  tone,
  pastel,
  icon,
}: {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  tone?: Tone;
  pastel?: Pastel;
  icon?: ReactNode;
}) {
  const alert = tone !== undefined && tone !== "neutral";
  return (
    <div
      className={cn(
        "rounded-3xl p-5",
        alert ? cn("border", toneStyles[tone]) : pastel ? pastelStyles[pastel] : "border border-line bg-white",
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="text-[13px] font-semibold text-ink/70">{label}</div>
        {icon && (
          <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-white text-ink shadow-soft">
            {icon}
          </span>
        )}
      </div>
      <div className="mt-2 text-[30px] font-extrabold leading-none tabular-nums tracking-tight text-ink">
        {value}
      </div>
      {hint && <div className="mt-2 text-xs text-ink/60">{hint}</div>}
    </div>
  );
}

/** Dark highlight card with one call to action (the "Earn now" card of the mock-up). */
export function HighlightCard({
  title,
  children,
  action,
  className,
}: {
  title: ReactNode;
  children?: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("relative overflow-hidden rounded-3xl bg-rail p-6 text-white", className)}>
      <div aria-hidden className="pointer-events-none absolute -bottom-10 -right-10 h-40 w-40 rounded-[36px] border border-white/15" />
      <div aria-hidden className="pointer-events-none absolute -bottom-4 right-10 h-28 w-28 rounded-[28px] border border-white/10" />
      <div className="relative">
        <div className="text-xl font-extrabold leading-snug">{title}</div>
        {children && <div className="mt-2 text-sm text-white/80">{children}</div>}
        {action && <div className="mt-5">{action}</div>}
      </div>
    </div>
  );
}

/** Progressive disclosure: closed by default, for details only some people need. */
export function Disclosure({
  title,
  children,
  defaultOpen = false,
}: {
  title: ReactNode;
  children: ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="border-t border-line">
      <button
        type="button"
        className="flex w-full items-center justify-between px-6 py-3.5 text-left text-sm font-medium text-muted hover:text-ink"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        {title}
        <ChevronDown size={16} className={cn("transition-transform", open && "rotate-180")} aria-hidden />
      </button>
      {open && <div className="px-6 pb-5">{children}</div>}
    </div>
  );
}

export function Tabs<T extends string>({
  value,
  onChange,
  items,
  fill = false,
}: {
  value: T;
  onChange: (v: T) => void;
  items: { value: T; label: string; count?: number }[];
  /** Equal-width tabs spanning the container (narrow panels). */
  fill?: boolean;
}) {
  return (
    <div role="tablist"
         className={cn("rounded-full bg-surface p-1", fill ? "grid" : "inline-flex flex-wrap")}
         style={fill ? { gridTemplateColumns: `repeat(${items.length}, minmax(0, 1fr))` } : undefined}>
      {items.map((it) => (
        <button
          key={it.value}
          role="tab"
          type="button"
          aria-selected={value === it.value}
          onClick={() => onChange(it.value)}
          className={cn(
            "truncate rounded-full py-1.5 text-sm transition-colors",
            fill ? "px-1 text-[13px]" : "px-4",
            value === it.value ? "bg-white font-semibold text-ink shadow-soft" : "text-muted hover:text-ink",
          )}
        >
          {it.label}
          {it.count !== undefined && <span className="ml-1.5 tabular-nums opacity-70">{it.count}</span>}
        </button>
      ))}
    </div>
  );
}

export function EmptyState({
  title,
  children,
  action,
}: {
  title: string;
  children?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <Card className="mx-auto max-w-lg px-8 py-10 text-center">
      <h2 className="text-xl font-bold">{title}</h2>
      {children && <div className="mt-2 text-sm text-muted">{children}</div>}
      {action && <div className="mt-5">{action}</div>}
    </Card>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded-3xl bg-line/60", className)} />;
}

export function PageSkeleton() {
  return (
    <div className="space-y-4" aria-busy="true" aria-label="Chargement">
      <Skeleton className="h-5 w-96" />
      <div className="grid gap-3 sm:grid-cols-4">
        {[0, 1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-28" />
        ))}
      </div>
      <Skeleton className="h-72" />
    </div>
  );
}

export function ErrorNotice({ error }: { error: unknown }) {
  const msg = error instanceof Error ? error.message : String(error);
  const rid =
    error && typeof error === "object" && "requestId" in error
      ? (error as { requestId?: string }).requestId
      : undefined;
  return (
    <Notice tone="urgent">
      {msg}
      {rid && <span className="ml-2 font-mono text-xs opacity-70">réf. {rid}</span>}
    </Notice>
  );
}

export const selectClass =
  "h-10 rounded-xl border border-line bg-white px-3 text-sm focus:outline-2 focus:outline-accent disabled:bg-surface";
export const inputClass =
  "h-10 w-full rounded-xl border border-line bg-white px-3 text-sm focus:outline-2 focus:outline-accent disabled:bg-surface";
