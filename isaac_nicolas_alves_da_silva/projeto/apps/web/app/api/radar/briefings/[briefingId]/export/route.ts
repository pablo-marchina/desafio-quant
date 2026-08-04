import { proxyRadarBinary } from "@/lib/api/radar-server";

export async function GET(_: Request, { params }: { params: Promise<{ briefingId: string }> }) {
  const { briefingId } = await params;
  return proxyRadarBinary(`/briefings/${encodeURIComponent(briefingId)}/export`);
}
