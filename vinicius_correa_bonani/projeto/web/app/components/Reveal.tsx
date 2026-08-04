"use client";

// Ilha de motion reutilizável. A página continua Server Component: ela só
// "embrulha" pedaços com <Reveal> e o conteúdo (children) segue renderizado
// no servidor; apenas a animação roda no cliente.
//
// Receita: opacity + translateY com spring sem bounce. NÃO animamos filter:
// blur aqui de propósito. Qualquer `filter` (mesmo blur(0px)) no wrapper
// isola o `backdrop-filter` dos cards de vidro filhos, o que quebra tanto a
// animação quanto o efeito de vidro. opacity+y não tem esse conflito.

import { motion, useReducedMotion } from "motion/react";

type RevealProps = {
  children: React.ReactNode;
  /** atraso em segundos, para stagger em listas (ex.: i * 0.05) */
  delay?: number;
  /** true = anima no carregamento (hero); false = anima ao entrar na viewport */
  immediate?: boolean;
  className?: string;
};

export default function Reveal({
  children,
  delay = 0,
  immediate = false,
  className,
}: RevealProps) {
  // Acessibilidade: com "reduzir movimento" ativo no sistema operacional,
  // devolvemos um <div> estático. Nada anima, o conteúdo só aparece.
  const reduce = useReducedMotion();
  if (reduce) return <div className={className}>{children}</div>;

  const visivel = { opacity: 1, y: 0 };

  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y: 16 }}
      {...(immediate
        ? { animate: visivel }
        : { whileInView: visivel, viewport: { once: true, amount: 0.2 } })}
      transition={{ type: "spring", duration: 0.5, bounce: 0, delay }}
    >
      {children}
    </motion.div>
  );
}
