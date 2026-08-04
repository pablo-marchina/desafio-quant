import "server-only";

const apiUrl = process.env.RADAR_API_URL;

if (!apiUrl) {
  throw new Error("RADAR_API_URL precisa ser configurada no ambiente do Next.js.");
}

export async function radarRequest(path: string, init?: RequestInit): Promise<Response> {
  const headers = new Headers(init?.headers);
  headers.set("content-type", "application/json");

  return fetch(`${apiUrl}${path}`, {
    ...init,
    headers,
    cache: "no-store",
  });
}

export async function proxyRadarRequest(path: string, init?: RequestInit): Promise<Response> {
  try {
    const response = await radarRequest(path, init);
    return new Response(await response.text(), {
      status: response.status,
      headers: { "content-type": response.headers.get("content-type") ?? "application/json" },
    });
  } catch {
    return Response.json(
      { detail: "A API do Radar nao esta acessivel. Verifique se o FastAPI esta rodando na porta configurada." },
      { status: 503 },
    );
  }
}

/**
 * Mesma ideia de proxyRadarRequest, mas para respostas binarias (ex: PDF do
 * export de briefing) — usar `.text()` corromperia os bytes.
 */
export async function proxyRadarBinary(path: string, init?: RequestInit): Promise<Response> {
  try {
    const response = await radarRequest(path, init);
    const headers = new Headers();
    headers.set("content-type", response.headers.get("content-type") ?? "application/octet-stream");
    const disposition = response.headers.get("content-disposition");
    if (disposition) headers.set("content-disposition", disposition);
    return new Response(response.body, { status: response.status, headers });
  } catch {
    return Response.json(
      { detail: "A API do Radar nao esta acessivel. Verifique se o FastAPI esta rodando na porta configurada." },
      { status: 503 },
    );
  }
}
