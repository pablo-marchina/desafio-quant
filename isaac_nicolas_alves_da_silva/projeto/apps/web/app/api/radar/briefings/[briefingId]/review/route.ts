import { proxyRadarRequest } from "@/lib/api/radar-server";

export async function PATCH(
  request: Request,
  { params }: { params: Promise<{ briefingId: string }> },
) {
  const { briefingId } = await params;
  return proxyRadarRequest(`/briefings/${encodeURIComponent(briefingId)}/review`, {
    method: "PATCH",
    body: await request.text(),
  });
}
