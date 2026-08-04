import type { Metadata } from "next";
import { Archivo, Geist_Mono } from "next/font/google";
import "./globals.css";

// next/font baixa os arquivos da fonte NO BUILD e serve do nosso domínio
// (self-hosted, sem request ao Google). "variable" expõe a fonte como
// variável CSS para o Tailwind consumir no globals.css.
const archivo = Archivo({
  variable: "--font-archivo",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "NVIDIA Startup AI Radar",
  description:
    "Inteligência de mercado para Startups & VCs: mapeia, qualifica e prioriza startups brasileiras de IA.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="pt-BR"
      className={`${archivo.variable} ${geistMono.variable} h-full antialiased`}
    >
      {/* suppressHydrationWarning: extensões de navegador (ex.: ColorZilla)
          injetam atributos no <body> antes do React hidratar, gerando um
          falso erro de hydration. Isso ignora só diferenças de ATRIBUTOS
          neste elemento; o conteúdo continua verificado normalmente. */}
      <body suppressHydrationWarning className="min-h-full flex flex-col">
        {children}
      </body>
    </html>
  );
}
