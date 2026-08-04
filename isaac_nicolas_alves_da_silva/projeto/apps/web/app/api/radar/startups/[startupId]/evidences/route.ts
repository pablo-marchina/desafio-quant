import { proxyRadarRequest } from "@/lib/api/radar-server";

export async function GET(_: Request, { params }: { params: Promise<{ startupId: string }> }) {
  const { startupId } = await params;
  return proxyRadarRequest(`/startups/${encodeURIComponent(startupId)}/evidences`);
}
