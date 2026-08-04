import { proxyRadarRequest } from "@/lib/api/radar-server";

export async function PATCH(
  request: Request,
  { params }: { params: Promise<{ recommendationId: string }> },
) {
  const { recommendationId } = await params;
  return proxyRadarRequest(`/recommendations/${encodeURIComponent(recommendationId)}/review`, {
    method: "PATCH",
    body: await request.text(),
  });
}
