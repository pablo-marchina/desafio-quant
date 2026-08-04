"use client";

// "use client" porque este componente usa estado (o texto digitado) e
// navegação programática. É a ÚNICA ilha interativa da landing; o resto
// da página continua renderizando no servidor.

import { useState } from "react";
import { useRouter } from "next/navigation";
import { MagnifyingGlassIcon } from "@phosphor-icons/react";

export default function SearchBox() {
  const [consulta, setConsulta] = useState("");
  const router = useRouter();

  // onSubmit no <form> captura tanto o Enter quanto o clique no botão.
  function buscar(e: React.FormEvent) {
    e.preventDefault(); // impede o reload de página do submit clássico
    const q = consulta.trim();
    router.push(q ? `/radar?q=${encodeURIComponent(q)}` : "/radar");
  }

  return (
    <form
      onSubmit={buscar}
      className="flex w-full max-w-2xl items-center gap-2 rounded-xl border border-line bg-[#0C0C0C] p-2 shadow-[inset_0_1px_0_rgba(255,255,255,0.06)] transition-colors focus-within:border-nvidia/60"
    >
      <MagnifyingGlassIcon size={20} className="ml-2 shrink-0 text-ink-muted" aria-hidden />
      <input
        type="text"
        value={consulta}
        onChange={(e) => setConsulta(e.target.value)}
        placeholder="Busque uma startup ou um tema, ex.: IA em saúde"
        aria-label="Buscar startup ou tema"
        className="w-full bg-transparent text-[15px] text-ink outline-none placeholder:text-ink-muted/70"
      />
      <button
        type="submit"
        className="shrink-0 rounded-lg bg-nvidia px-4 py-2 text-sm font-semibold text-black transition-colors hover:bg-nvidia-bright active:translate-y-px"
      >
        Analisar
      </button>
    </form>
  );
}
