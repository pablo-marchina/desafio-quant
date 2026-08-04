"use client";

// A navbar nasce transparente sobre o hero e só ganha fundo (blur + borda)
// DEPOIS que a sequência de abertura termina. Como durante a animação o palco
// fica preso (sticky) e a tela parece parada, um limiar fixo de scroll acendia
// o fundo cedo demais. Então observamos um marcador (#hero-end) posto logo
// depois da sequência: enquanto ele não cruza a base da navbar, ficamos
// transparentes. IntersectionObserver não é listener de scroll (não roda a
// cada frame), então segue a regra do projeto.

import Link from "next/link";
import { useEffect, useState } from "react";
import { useReducedMotion } from "motion/react";

const NAV_H = 64; // precisa bater com o h-16 do <nav>

export default function Navbar() {
  const [rolou, setRolou] = useState(false);
  const reduce = useReducedMotion();

  useEffect(() => {
    const alvo = document.getElementById("hero-end");
    if (!alvo) return;
    // rootMargin recua o topo da "área de observação" até a base da navbar;
    // top < NAV_H significa que o marcador já subiu para além dela.
    const io = new IntersectionObserver(
      ([e]) => setRolou(e.boundingClientRect.top < NAV_H),
      { rootMargin: `-${NAV_H}px 0px 0px 0px` }
    );
    io.observe(alvo);
    return () => io.disconnect();
  }, []);

  return (
    <nav
      className={`sticky top-0 z-40 border-b ${
        rolou
          ? "border-line bg-bg/85 backdrop-blur"
          : "border-transparent bg-transparent"
      } ${reduce ? "" : "transition-colors duration-200"}`}
    >
      <div className="mx-auto flex h-16 max-w-[1400px] items-center justify-between px-6">
        <div className="flex items-center gap-8">
          <Link href="/" className="flex items-center gap-2.5">
            <img src="/nvidia-logo.png" alt="NVIDIA" className="h-5 w-auto" />
            <span className="text-[15px] font-semibold tracking-tight">
              Startup AI Radar
            </span>
          </Link>

          <div className="hidden items-center gap-6 text-sm text-ink-muted md:flex">
            <Link href="/#como-funciona" className="transition-colors hover:text-ink">
              Como funciona
            </Link>
            <Link href="/#stack" className="transition-colors hover:text-ink">
              Stack
            </Link>
            <Link href="/#metodologia" className="transition-colors hover:text-ink">
              Metodologia
            </Link>
          </div>
        </div>

        <Link
          href="/radar"
          className="rounded-lg border border-nvidia/70 px-4 py-2 text-sm font-semibold text-ink transition-colors hover:border-nvidia hover:bg-nvidia/10 active:translate-y-px"
        >
          Abrir o Radar
        </Link>
      </div>
    </nav>
  );
}
