import { proxyRadarRequest } from "@/lib/api/radar-server";

export async function POST() {
  return proxyRadarRequest("/startup-discovery/runs", { method: "POST", body: "{}" });
}
