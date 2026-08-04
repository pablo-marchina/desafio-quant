import Link from "next/link";
import ConstellationBg from "../components/ConstellationBg";
import AnaliseProvider from "./AnaliseProvider";

// Header próprio do dashboard: transparente (as "estrelas" aparecem através
// dele). Como ele é sticky e a tabela rola por baixo, o único fundo é um
// scrim de gradiente suave que esmaece o conteúdo sem virar barra dura.
// O logo leva de volta ao site (por isso não existe botão "Voltar").
export default function RadarLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-dvh">
      <ConstellationBg />
      {/* glow verde sutil no topo, atrás de tudo */}
      <div className="pointer-events-none fixed inset-0 -z-20 bg-[radial-gradient(55%_40%_at_50%_0%,rgba(118,185,0,0.10),transparent_70%)]" />

      <header className="sticky top-0 z-40 bg-gradient-to-b from-bg via-bg/60 to-transparent">
        <div className="mx-auto flex h-16 max-w-[1400px] items-center px-6">
          <Link href="/" className="flex items-center gap-2.5">
            <img src="/nvidia-logo.png" alt="NVIDIA" className="h-5 w-auto" />
            <span className="text-[15px] font-semibold tracking-tight">
              Startup AI Radar
            </span>
          </Link>
        </div>
      </header>

      {/* o provider vive no layout: sobrevive à navegação entre as abas,
          então uma análise em andamento não morre ao trocar de página */}
      <AnaliseProvider>{children}</AnaliseProvider>
    </div>
  );
}
