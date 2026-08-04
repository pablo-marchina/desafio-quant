import { createFileRoute } from "@tanstack/react-router";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { SectionTitle, ContactStatusBadge } from "@/components/ui-bits";
import { useContacts } from "@/lib/contacts-store";
import { startups } from "@/lib/mock-data";
import { Mail, Phone, MapPin, Building2, Shield, Clock } from "lucide-react";
import { useMemo } from "react";

export const Route = createFileRoute("/profile")({
  head: () => ({ meta: [{ title: "Perfil — NVIDIA Toph" }] }),
  component: ProfilePage,
});

function ProfilePage() {
  const contacts = useContacts();
  const stats = useMemo(() => {
    const entries = Object.entries(contacts);
    const byStatus: Record<string, number> = {};
    for (const [, rec] of entries) byStatus[rec.status] = (byStatus[rec.status] || 0) + 1;
    return {
      total: entries.length,
      negociando: byStatus["Em negociação"] || 0,
      fechados: byStatus["Contrato fechado"] || 0,
      recentes: entries
        .map(([id, rec]) => ({ id, rec, startup: startups.find((s) => s.id === id) }))
        .filter((x) => x.startup)
        .sort((a, b) => b.rec.updatedAt.localeCompare(a.rec.updatedAt))
        .slice(0, 5),
    };
  }, [contacts]);

  return (
    <div className="mx-auto w-full max-w-5xl space-y-5 p-4 md:p-6">
      <Card className="p-5">
        <div className="flex flex-wrap items-start gap-5">
          <div
            className="grid h-20 w-20 shrink-0 place-items-center rounded-full text-2xl font-semibold text-white"
            style={{ background: "linear-gradient(135deg, #76B900, #4d7a00)" }}
          >
            AR
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-xl font-semibold text-foreground">Ana Ribeiro</h1>
              <Badge variant="outline" className="border-primary/30 bg-primary/5 text-[10px] text-primary">
                <Shield className="mr-1 h-3 w-3" /> Analista Sênior
              </Badge>
            </div>
            <p className="mt-1 text-sm text-muted-foreground">Startup Intelligence · NVIDIA LATAM</p>
            <div className="mt-3 grid gap-1 text-xs text-foreground sm:grid-cols-2">
              <div className="flex items-center gap-2"><Mail className="h-3.5 w-3.5 text-muted-foreground" /> ana.ribeiro@nvidia.fict</div>
              <div className="flex items-center gap-2"><Phone className="h-3.5 w-3.5 text-muted-foreground" /> +55 11 99000-1122</div>
              <div className="flex items-center gap-2"><Building2 className="h-3.5 w-3.5 text-muted-foreground" /> Time: LATAM Inception</div>
              <div className="flex items-center gap-2"><MapPin className="h-3.5 w-3.5 text-muted-foreground" /> São Paulo, SP</div>
            </div>
          </div>
          <div className="grid grid-cols-3 gap-2 text-center">
            <div className="rounded-md border border-border px-3 py-2">
              <p className="text-[10px] uppercase tracking-wider text-muted-foreground">Empresas</p>
              <p className="text-lg font-semibold tabular-nums text-foreground">{stats.total}</p>
            </div>
            <div className="rounded-md border border-border px-3 py-2">
              <p className="text-[10px] uppercase tracking-wider text-muted-foreground">Negociando</p>
              <p className="text-lg font-semibold tabular-nums text-foreground">{stats.negociando}</p>
            </div>
            <div className="rounded-md border border-primary/30 bg-primary/5 px-3 py-2">
              <p className="text-[10px] uppercase tracking-wider text-primary">Fechados</p>
              <p className="text-lg font-semibold tabular-nums text-primary">{stats.fechados}</p>
            </div>
          </div>
        </div>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="p-5">
          <SectionTitle title="Dados da conta" desc="Mock — somente leitura nesta demo" />
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label className="text-xs">Nome</Label>
              <Input defaultValue="Ana Ribeiro" disabled />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">E-mail corporativo</Label>
              <Input defaultValue="ana.ribeiro@nvidia.fict" disabled />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">Cargo</Label>
              <Input defaultValue="Analista Sênior" disabled />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">Time</Label>
              <Input defaultValue="LATAM Inception" disabled />
            </div>
          </div>
          <Separator className="my-4" />
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-xs text-muted-foreground">Sessão iniciada há 2h 14min · 2FA ativo</p>
            <Button size="sm" variant="outline">Editar perfil</Button>
          </div>
        </Card>

        <Card className="p-5">
          <SectionTitle title="Atividade recente" desc="Últimas mudanças de status em contatos" />
          <div className="divide-y divide-border">
            {stats.recentes.map(({ id, rec, startup }) => (
              <div key={id} className="flex items-center justify-between gap-3 py-2.5">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-foreground">{startup!.name}</p>
                  <p className="flex items-center gap-1 text-[11px] text-muted-foreground">
                    <Clock className="h-3 w-3" />
                    {rec.updatedAt ? new Date(rec.updatedAt).toLocaleString("pt-BR") : "—"}
                  </p>
                </div>
                <ContactStatusBadge status={rec.status} />
              </div>
            ))}
            {stats.recentes.length === 0 && (
              <p className="py-6 text-center text-xs text-muted-foreground">Nenhuma atividade ainda.</p>
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}
