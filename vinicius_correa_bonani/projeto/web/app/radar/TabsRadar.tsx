"use client";

// Navegação por abas estilo NVIDIA: cada aba é uma ROTA de verdade (URL
// própria, compartilhável), e o usePathname() diz qual está ativa para
// pintar o sublinhado verde. O truque visual: a barra tem uma linha cinza
// embaixo (border-b) e cada aba tem uma borda de 2px puxada 1px para baixo
// (-mb-px), então a linha verde da ativa SOBREPÕE a cinza, como no site
// da NVIDIA.

import Link from "next/link";
import { usePathname } from "next/navigation";

const ABAS = [
  { rotulo: "Ranking", href: "/radar" },
  { rotulo: "Descoberta", href: "/radar/descoberta" },
];

export default function TabsRadar() {
  const pathname = usePathname();

  return (
    <nav aria-label="Seções do radar" className="border-b border-line">
      <div className="flex gap-6">
        {ABAS.map((aba) => {
          const ativa = pathname === aba.href;
          return (
            <Link
              key={aba.href}
              href={aba.href}
              aria-current={ativa ? "page" : undefined}
              className={`-mb-px border-b-2 pb-3 text-sm font-medium transition-colors ${
                ativa
                  ? "border-nvidia text-ink"
                  : "border-transparent text-ink-muted hover:text-ink"
              }`}
            >
              {aba.rotulo}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
