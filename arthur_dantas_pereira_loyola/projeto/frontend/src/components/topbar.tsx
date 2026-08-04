import { Search, Download, Database } from "lucide-react";
import { SidebarTrigger } from "@/components/ui/sidebar";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { startups } from "@/lib/mock-data";

export function Topbar() {
  const navigate = useNavigate();
  const [q, setQ] = useState("");

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const match =
      startups.find((s) => s.name.toLowerCase().includes(q.toLowerCase())) ?? startups[0];
    navigate({ to: "/startup/$id", params: { id: match.id } });
  };

  return (
    <header className="sticky top-0 z-30 flex h-14 shrink-0 items-center gap-3 border-b border-border bg-background/80 px-3 backdrop-blur md:px-4">
      <SidebarTrigger />
      <Separator orientation="vertical" className="h-6" />
      <div className="flex min-w-0 items-center gap-2">
        <span className="hidden text-sm font-semibold text-foreground md:inline">NVIDIA Toph</span>
        <Badge variant="outline" className="hidden gap-1 border-primary/30 bg-primary/5 text-[10px] font-medium text-primary md:inline-flex">
          <Database className="h-3 w-3" /> Demo data
        </Badge>
      </div>

      <form onSubmit={onSubmit} className="ml-auto flex min-w-0 flex-1 items-center justify-end gap-2 md:max-w-xl">
        <div className="relative w-full">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Busca rápida por startup, setor, evidência…"
            className="h-9 pl-8"
          />
        </div>
      </form>

      <Button size="sm" className="gap-1.5" onClick={() => navigate({ to: "/briefing" })}>
        <Download className="h-4 w-4" />
        <span className="hidden sm:inline">Export briefing</span>
      </Button>
    </header>
  );
}
