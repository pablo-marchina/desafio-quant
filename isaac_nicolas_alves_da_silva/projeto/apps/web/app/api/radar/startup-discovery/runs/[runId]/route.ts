import { proxyRadarRequest } from "@/lib/api/radar-server";

export async function GET(_: Request, { params }: { params: Promise<{ runId: string }> }) {
  const { runId } = await params;
  return proxyRadarRequest(`/startup-discovery/runs/${encodeURIComponent(runId)}`);
}
