import { proxyRadarRequest } from "@/lib/api/radar-server";

export async function GET(request: Request) {
  const query = new URL(request.url).search;
  return proxyRadarRequest(`/startups${query}`);
}
