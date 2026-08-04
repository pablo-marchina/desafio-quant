"use client";

// Ilha cliente: baixar arquivo é uma ação do navegador (criar um Blob em
// memória e disparar um clique). A página (Server Component) passa o texto
// do briefing por props; só este botão roda no cliente.

import { DownloadSimpleIcon } from "@phosphor-icons/react";

export default function BaixarBriefing({
  nome,
  briefing,
}: {
  nome: string;
  briefing: string;
}) {
  function baixar() {
    // Blob = o conteúdo do arquivo em memória; createObjectURL dá uma URL
    // temporária que um <a download> usa para salvar no disco.
    const blob = new Blob([briefing], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    // nome de arquivo seguro: espaços/pontos/barras viram "_"
    a.download = `briefing-${nome.replace(/[^\w-]+/g, "_")}.md`;
    a.click();
    URL.revokeObjectURL(url); // libera a memória do Blob
  }

  return (
    <button
      onClick={baixar}
      className="inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-nvidia/70 px-3 py-2 text-sm font-medium text-ink transition-colors hover:border-nvidia hover:bg-nvidia/10 active:translate-y-px"
    >
      <DownloadSimpleIcon size={15} className="text-nvidia" aria-hidden />
      Baixar .md
    </button>
  );
}
