import type { Metadata } from "next";
import { Inter } from "next/font/google";

import { Providers } from "@/components/providers";
import { Sidebar } from "@/components/sidebar";
import { Topbar } from "@/components/topbar";
import "@/app/globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata: Metadata = {
  title: "Start and Up",
  description: "Painel de inteligencia de startups para parcerias",
  icons: {
    icon: "/start-and-up.png",
    shortcut: "/start-and-up.png",
    apple: "/start-and-up.png"
  }
};

export default function RootLayout({
  children
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="pt-BR" className="dark">
      <body className={inter.variable}>
        <Providers>
          <Sidebar />
          <div className="min-h-screen min-w-0 overflow-x-hidden lg:pl-[230px]">
            <Topbar />
            {children}
          </div>
        </Providers>
      </body>
    </html>
  );
}
