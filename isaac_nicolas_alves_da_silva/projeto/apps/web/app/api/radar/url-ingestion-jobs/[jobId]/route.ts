import { proxyRadarRequest } from "@/lib/api/radar-server";

export async function GET(_: Request, { params }: { params: Promise<{ jobId: string }> }) {
  const { jobId } = await params;
  return proxyRadarRequest(`/url-ingestion/jobs/${encodeURIComponent(jobId)}`);
}
