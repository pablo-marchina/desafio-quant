import type { Metadata } from "next";
import Link from "next/link";

import "./globals.css";
import { QueryProvider } from "@/providers/query-provider";

export const metadata: Metadata = {
  title: "NVIDIA Startup AI Radar",
  description: "Analise startups e encontre oportunidades NVIDIA.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="pt-BR">
      <body>
        <QueryProvider>
          <header className="border-b border-[var(--surface-border)] bg-[#07111f]/90">
            <nav className="mx-auto flex max-w-6xl items-center justify-between gap-6 px-6 py-4">
              <Link className="font-semibold tracking-tight" href="/">
                <span className="text-[var(--accent)]">NVIDIA</span> Startup AI Radar
              </Link>
              <div className="flex items-center gap-5 text-sm text-[var(--muted)]">
                <Link className="hover:text-white" href="/startups">Portfolio</Link>
                <Link className="hover:text-white" href="/dashboard">Dashboard</Link>
                <Link className="hover:text-white" href="/discovery">Descoberta</Link>
                <Link className="hover:text-white" href="/jobs">Historico</Link>
                <Link className="hover:text-white" href="/knowledge">Chat NVIDIA</Link>
              </div>
              <Link className="rounded-md bg-[var(--accent)] px-4 py-2 text-sm font-semibold text-[#07111f]" href="/analyze">
                Analisar startup
              </Link>
            </nav>
          </header>
          {children}
        </QueryProvider>
      </body>
    </html>
  );
}
