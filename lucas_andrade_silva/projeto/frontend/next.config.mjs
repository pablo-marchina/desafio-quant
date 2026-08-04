import path from "node:path";
import nextEnv from "@next/env";

// O projeto mantém uma única configuração de ambiente na raiz do repositório.
const { loadEnvConfig } = nextEnv;
loadEnvConfig(path.resolve(process.cwd(), ".."));

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  env: {
    NEXT_PUBLIC_API_URL:
      process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000"
  }
};

export default nextConfig;
