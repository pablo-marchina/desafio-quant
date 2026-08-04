import { useState } from "react";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import type { AIMaturity } from "@/lib/mock-data";
import { getCompanyExtras } from "@/lib/company-extras";
import { CONTACT_STATUSES, STATUS_COLORS, type ContactStatus } from "@/lib/contacts-store";

export function ScoreBar({ value, className }: { value: number; className?: string }) {
  const color =
    value >= 80 ? "bg-primary" : value >= 60 ? "bg-info" : value >= 40 ? "bg-warning" : "bg-destructive";
  return (
    <div className={cn("flex items-center gap-2", className)}>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
        <div className={cn("h-full rounded-full", color)} style={{ width: `${Math.min(100, Math.max(0, value))}%` }} />
      </div>
      <span className="w-8 shrink-0 text-right text-xs font-medium tabular-nums text-foreground">{value}</span>
    </div>
  );
}

export function MaturityBadge({ value }: { value: AIMaturity }) {
  const map: Record<AIMaturity, string> = {
    "AI-Native": "border-primary/40 bg-primary/10 text-primary",
    "AI-Enabled": "border-info/40 bg-info/10 text-info",
    "Non-AI": "border-border bg-muted text-muted-foreground",
  };
  return (
    <Badge variant="outline" className={cn("font-medium", map[value])}>
      {value}
    </Badge>
  );
}

export function StatusDot({ status }: { status: string }) {
  const map: Record<string, string> = {
    completed: "bg-primary",
    running: "bg-info animate-pulse",
    "needs evidence": "bg-warning",
    blocked: "bg-destructive",
    ready: "bg-muted-foreground/60",
    validada: "bg-primary",
    fraca: "bg-warning",
    contraditória: "bg-destructive",
    pendente: "bg-muted-foreground/60",
  };
  return <span className={cn("inline-block h-2 w-2 rounded-full", map[status] ?? "bg-muted")} />;
}

export function SectionTitle({ title, desc, right, icon }: { title: string | React.ReactNode; desc?: string; right?: React.ReactNode; icon?: React.ReactNode }) {
  return (
    <div className="mb-3 flex items-end justify-between gap-3">
      <div className="min-w-0">
        <h2 className="flex items-center gap-2 truncate text-sm font-semibold text-foreground">{icon}{title}</h2>
        {desc && <p className="text-xs text-muted-foreground">{desc}</p>}
      </div>
      {right}
    </div>
  );
}

function initialsFor(name: string): string {
  const parts = name.replace(/[^\w\s]/g, "").split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "??";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[1][0]).toUpperCase();
}

const SIZE_MAP = {
  xs: "h-6 w-6 text-[10px]",
  sm: "h-8 w-8 text-xs",
  md: "h-10 w-10 text-sm",
  lg: "h-14 w-14 text-base",
} as const;

export function CompanyLogo({
  id,
  name,
  size = "sm",
  className,
  domain: explicitDomain,
}: {
  id: string;
  name: string;
  size?: keyof typeof SIZE_MAP;
  className?: string;
  domain?: string;
}) {
  const { brandColor, domain: extrasDomain } = getCompanyExtras(id, name);
  const domain = explicitDomain ?? extrasDomain;
  const initials = initialsFor(name);
  const logoUrl = `https://www.google.com/s2/favicons?domain=${domain}&sz=64`;
  const [imgError, setImgError] = useState(false);

  if (!imgError) {
    return (
      <div
        className={cn(
          "grid shrink-0 place-items-center overflow-hidden rounded-md",
          SIZE_MAP[size],
          className,
        )}
        aria-label={name}
        role="img"
      >
        <img
          src={logoUrl}
          alt={name}
          className="h-full w-full object-contain"
          onError={() => setImgError(true)}
        />
      </div>
    );
  }

  return (
    <div
      className={cn(
        "grid shrink-0 place-items-center rounded-md font-semibold text-white ring-1 ring-inset ring-black/5",
        SIZE_MAP[size],
        className,
      )}
      style={{ background: `linear-gradient(135deg, ${brandColor}, ${brandColor}cc)` }}
      aria-label={name}
      role="img"
    >
      {initials}
    </div>
  );
}

export function ContactStatusBadge({ status }: { status: ContactStatus }) {
  return (
    <Badge variant="outline" className={cn("font-medium", STATUS_COLORS[status])}>
      {status}
    </Badge>
  );
}

export { CONTACT_STATUSES };
