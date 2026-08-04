"use client";

import { useEffect, useMemo, useState } from "react";

import { cn, normalizeDomain } from "@/lib/utils";

const PLACEHOLDER_LOGO = "/placeholder-logo.png";

type StartupLogoProps = {
  website?: string | null;
  name?: string | null;
  className?: string;
  imageClassName?: string;
};

export function StartupLogo({
  website,
  name,
  className,
  imageClassName
}: StartupLogoProps) {
  const sources = useMemo(() => {
    const domain = normalizeDomain(website);
    if (!domain) return [PLACEHOLDER_LOGO];

    return [
      `https://logo.clearbit.com/${domain}`,
      `https://www.google.com/s2/favicons?domain=${domain}&sz=128`,
      `https://icons.duckduckgo.com/ip3/${domain}.ico`,
      PLACEHOLDER_LOGO
    ];
  }, [website]);
  const [sourceIndex, setSourceIndex] = useState(0);
  const src = sources[Math.min(sourceIndex, sources.length - 1)];

  useEffect(() => {
    setSourceIndex(0);
  }, [sources]);

  return (
    <div
      className={cn(
        "grid shrink-0 place-items-center overflow-hidden rounded-md border border-border bg-white/[0.025]",
        className
      )}
    >
      <img
        alt={name ? `Logo da ${name}` : "Logo da startup"}
        className={cn("h-full w-full object-contain p-1.5", imageClassName)}
        src={src}
        onError={() => {
          setSourceIndex((current) =>
            current < sources.length - 1 ? current + 1 : current
          );
        }}
      />
    </div>
  );
}
