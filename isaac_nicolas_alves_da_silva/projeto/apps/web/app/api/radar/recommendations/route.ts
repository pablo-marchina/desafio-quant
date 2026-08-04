import { proxyRadarRequest } from "@/lib/api/radar-server";

export async function GET(request: Request) {
  const startupId = new URL(request.url).searchParams.get("startup_id");
  if (!startupId) return Response.json({ detail: "startup_id e obrigatorio." }, { status: 400 });
  return proxyRadarRequest(`/recommendations?startup_id=${encodeURIComponent(startupId)}`);
}

export async function POST(request: Request) {
  return proxyRadarRequest("/recommendations", { method: "POST", body: await request.text() });
}
