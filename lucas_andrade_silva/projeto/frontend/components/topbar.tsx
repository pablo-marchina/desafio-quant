"use client";

import { CircleHelp, Search } from "lucide-react";

import { Input } from "@/components/ui/input";
import { useUserSession } from "@/lib/user-session";

export function Topbar() {
  const { initials } = useUserSession();

  return (
    <header className="sticky top-0 z-30 flex h-[74px] min-w-0 items-center gap-2 border-b border-border bg-background/90 px-4 backdrop-blur-xl lg:px-8">
      <div className="relative ml-12 min-w-0 flex-1 max-w-[510px] lg:ml-0">
        <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          aria-label="Busca global"
          className="h-10 pl-10 pr-16"
          placeholder="Buscar startups, domínios, tecnologias..."
        />
        <span className="absolute right-3 top-1/2 -translate-y-1/2 rounded border border-border bg-white/[0.03] px-1.5 py-0.5 text-[10px] text-muted-foreground">
          ⌘ K
        </span>
      </div>
      <div className="ml-auto flex items-center gap-2">
        <button
          className="grid size-9 place-items-center rounded-md text-muted-foreground hover:bg-white/[0.04] hover:text-foreground"
          aria-label="Ajuda"
        >
          <CircleHelp className="size-[18px]" />
        </button>
        <div className="ml-2 hidden size-9 place-items-center rounded-full bg-white/[0.07] text-xs font-semibold text-primary sm:grid">
          {initials}
        </div>
      </div>
    </header>
  );
}
