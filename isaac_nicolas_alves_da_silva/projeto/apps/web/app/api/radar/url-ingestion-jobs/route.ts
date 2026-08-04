import { proxyRadarRequest } from "@/lib/api/radar-server";

export async function GET(request: Request) {
  const query = new URL(request.url).search;
  return proxyRadarRequest(`/url-ingestion/jobs${query}`);
}

export async function POST(request: Request) {
  const body = await request.text();
  return proxyRadarRequest("/url-ingestion/jobs", { method: "POST", body });
}
