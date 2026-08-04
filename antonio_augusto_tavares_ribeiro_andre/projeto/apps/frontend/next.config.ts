import path from "node:path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Fixa a raiz no diretorio do app: ha outros lockfiles na arvore (raiz do repo,
  // home do usuario) e sem isso o Next infere o workspace root errado.
  turbopack: {
    root: path.join(__dirname),
  },
};

export default nextConfig;
