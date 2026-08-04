import { proxyRadarRequest } from "@/lib/api/radar-server";

export async function GET() {
  return proxyRadarRequest("/startups/stats");
}
