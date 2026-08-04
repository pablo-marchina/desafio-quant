"use client";

import {
  Database,
  FileBarChart,
  Lightbulb,
  LayoutDashboard,
  Menu,
  Scale,
  X
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, type MouseEvent } from "react";

import { useNavigationLoading } from "@/components/navigation-loading";
import { Button } from "@/components/ui/button";
import { useUserSession } from "@/lib/user-session";
import { cn } from "@/lib/utils";

const mainItems = [
  { label: "Visão Geral", icon: LayoutDashboard, href: "/" },
  { label: "Startups", icon: Database, href: "/startups" },
  { label: "VS Big Techs", icon: Scale, href: "/big-techs" },
  { label: "Recomendações", icon: Lightbulb, href: "/recomendacoes" },
  { label: "Relatórios", icon: FileBarChart, href: "/relatorios" }
];

export function Sidebar() {
  const [open, setOpen] = useState(false);
  const pathname = usePathname();
  const { startLoading } = useNavigationLoading();
  const { clearUserName, initials, userName } = useUserSession();

  const handleNavigationClick = (
    event: MouseEvent<HTMLAnchorElement>,
    href: string,
    active: boolean
  ) => {
    setOpen(false);
    if (
      active ||
      event.defaultPrevented ||
      event.button !== 0 ||
      event.metaKey ||
      event.ctrlKey ||
      event.shiftKey ||
      event.altKey
    ) {
      return;
    }
    startLoading();
  };

  return (
    <>
      <Button
        aria-label="Abrir menu"
        className="fixed left-4 top-3 z-50 lg:hidden"
        size="icon"
        variant="outline"
        onClick={() => setOpen(true)}
      >
        <Menu className="size-4" />
      </Button>
      {open && (
        <button
          aria-label="Fechar menu"
          className="fixed inset-0 z-40 bg-black/70 lg:hidden"
          onClick={() => setOpen(false)}
        />
      )}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-40 flex w-[230px] -translate-x-full flex-col border-r border-border bg-[#070c12] transition-transform lg:translate-x-0",
          open && "translate-x-0"
        )}
      >
        <div className="flex h-[74px] items-center gap-3 border-b border-border px-5">
          <Link
            aria-label="Ir para visão geral"
            className="min-w-0 overflow-hidden rounded-md border border-primary/20 bg-white/[0.03]"
            href="/"
            onClick={(event) =>
              handleNavigationClick(event, "/", pathname === "/")
            }
          >
            <img
              alt="Start and Up"
              className="h-11 w-[156px] object-cover object-center"
              src="/start-and-up.png"
            />
          </Link>
          <button
            className="ml-auto lg:hidden"
            aria-label="Fechar menu"
            onClick={() => setOpen(false)}
          >
            <X className="size-4" />
          </button>
        </div>

        <nav className="flex-1 overflow-y-auto px-3 py-6">
          <p className="mb-2 px-3 text-[10px] uppercase tracking-wider text-muted-foreground">
            Principal
          </p>
          <div className="space-y-1">
            {mainItems.map(({ label, icon: Icon, href }) => {
              const active =
                href === "/"
                  ? pathname === "/"
                  : href
                    ? pathname.startsWith(href)
                    : false;
              const className = cn(
                "flex h-10 w-full items-center gap-3 rounded-md px-3 text-left text-sm text-muted-foreground transition hover:bg-white/[0.04] hover:text-foreground",
                active && "bg-primary/15 text-foreground"
              );
              return href ? (
                <Link
                  key={label}
                  href={href}
                  className={className}
                  onClick={(event) =>
                    handleNavigationClick(event, href, active)
                  }
                >
                  <Icon className={cn("size-4", active && "text-primary")} />
                  {label}
                </Link>
              ) : (
                <button key={label} className={className}>
                  <Icon className="size-4" />
                  {label}
                </button>
              );
            })}
          </div>
        </nav>

        <div className="m-3 flex items-center gap-3 rounded-lg border border-border bg-white/[0.02] p-3">
          <div className="relative grid size-9 shrink-0 place-items-center rounded-full bg-white/[0.07] text-xs font-semibold">
            {initials}
            <span className="absolute bottom-0 right-0 size-2 rounded-full border-2 border-[#0b1118] bg-primary" />
          </div>
          <div className="min-w-0">
            <p className="truncate text-xs font-medium">Sessão ativa</p>
            <p className="truncate text-[10px] text-muted-foreground">
              {userName}
            </p>
          </div>
          <button
            className="ml-auto rounded px-2 py-1 text-[10px] text-muted-foreground hover:bg-white/[0.04] hover:text-foreground"
            onClick={clearUserName}
          >
            Trocar
          </button>
        </div>
      </aside>
    </>
  );
}
