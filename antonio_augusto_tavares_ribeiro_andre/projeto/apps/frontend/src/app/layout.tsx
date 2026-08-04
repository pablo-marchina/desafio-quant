import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

import { AuthGate } from "@/components/auth-gate";

// Variaveis consumidas pelo @theme do globals.css (--font-sans / --font-mono).
const geistSans = Geist({
  variable: "--font-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-mono",
  subsets: ["latin"],
});

// UI em PT-BR (F0.13): publico e o gerente de Startups & VCs da NVIDIA Brasil.
export const metadata: Metadata = {
  title: "NVIDIA Startup AI Radar",
  description:
    "Painel interno para mapear startups brasileiras AI-native, diagnosticar " +
    "maturidade tecnica (AIMI) e recomendar tecnologias NVIDIA para o Inception.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="pt-BR"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        {/* Gate interno (F5.9): so libera as telas quando a API nao exige credencial ou o
            gerente entrou com o token. Client component envolvendo os children server (padrao
            de provider do App Router). */}
        <AuthGate>{children}</AuthGate>
      </body>
    </html>
  );
}
