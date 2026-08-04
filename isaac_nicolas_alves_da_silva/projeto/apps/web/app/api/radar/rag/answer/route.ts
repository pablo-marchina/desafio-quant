import { proxyRadarRequest } from "@/lib/api/radar-server";

export async function POST(request: Request) {
  return proxyRadarRequest("/rag/answer", { method: "POST", body: await request.text() });
}
