"use client";

// Gráfico de radar em SVG puro, sem biblioteca: com 4 eixos fixos a 90°,
// cada ponto é trigonometria de círculo unitário (cos/sin), e uma lib de
// charts inteira não se justifica.
//
// Paleta validada pelo script da skill dataviz (modo dark, superfície
// #0C0C0C, todos os pares): verde #69A500, azul #3987e5, magenta #d55181.
// O par mais fraco (tritan 7.2) exige codificação secundária, cumprida com
// a legenda, o swatch junto ao nome e o anel de 2px nos vértices.

export const CORES_SERIES = ["#69A500", "#3987e5", "#d55181"];

export type SerieRadar = {
  nome: string;
  cor: string;
  notas: Record<string, number>;
};

const EIXOS_RADAR = [
  { key: "ai_native", label: "AI-Native" },
  { key: "nvidia_fit", label: "NVIDIA-Fit" },
  { key: "tracao", label: "Tração" },
  { key: "time_ia", label: "Time de IA" },
];

// o palco é mais largo (400) que alto: os rótulos "NVIDIA-Fit" e "Time de IA"
// ficam FORA do raio, nas laterais, e precisam dessa folga horizontal para
// não serem cortados pela borda do viewBox
const CX = 200;
const CY = 150;
const R = 104;
// topo, direita, base, esquerda (em graus; -90 = para cima)
const ANGULOS = [-90, 0, 90, 180];

// converte (eixo, valor 0..10) na coordenada x,y daquele ponto
function ponto(eixo: number, valor: number): [number, number] {
  const rad = (ANGULOS[eixo] * Math.PI) / 180;
  const dist = (Math.max(0, Math.min(10, valor)) / 10) * R;
  return [CX + dist * Math.cos(rad), CY + dist * Math.sin(rad)];
}

// "x1,y1 x2,y2 x3,y3 x4,y4" para <polygon>
function poligono(valores: number[]): string {
  return valores
    .map((v, i) => ponto(i, v).map((n) => n.toFixed(1)).join(","))
    .join(" ");
}

export default function GraficoRadar({ series }: { series: SerieRadar[] }) {
  return (
    <figure className="mx-auto max-w-[440px]">
      <svg
        viewBox="0 0 400 300"
        role="img"
        aria-label={`Radar das notas de ${series.map((s) => s.nome).join(", ")}`}
      >
        {/* anéis de grade: um losango a cada 2.5 pontos */}
        {[2.5, 5, 7.5, 10].map((nivel) => (
          <polygon
            key={nivel}
            points={poligono([nivel, nivel, nivel, nivel])}
            fill="none"
            className="stroke-line"
            strokeWidth={1}
          />
        ))}

        {/* linhas dos eixos, do centro ao vértice máximo */}
        {EIXOS_RADAR.map((_, i) => {
          const [x, y] = ponto(i, 10);
          return (
            <line
              key={i}
              x1={CX}
              y1={CY}
              x2={x}
              y2={y}
              className="stroke-line"
              strokeWidth={1}
            />
          );
        })}

        {/* escala no eixo do topo (só 5 e 10, para não poluir) */}
        {[5, 10].map((nivel) => (
          <text
            key={nivel}
            x={CX + 5}
            y={CY - (nivel / 10) * R - 3}
            className="fill-ink-muted font-mono"
            fontSize={9}
          >
            {nivel}
          </text>
        ))}

        {/* rótulos dos 4 eixos */}
        <text x={CX} y={CY - R - 12} textAnchor="middle" className="fill-ink-muted" fontSize={11}>
          {EIXOS_RADAR[0].label}
        </text>
        <text x={CX + R + 10} y={CY + 4} textAnchor="start" className="fill-ink-muted" fontSize={11}>
          {EIXOS_RADAR[1].label}
        </text>
        <text x={CX} y={CY + R + 20} textAnchor="middle" className="fill-ink-muted" fontSize={11}>
          {EIXOS_RADAR[2].label}
        </text>
        <text x={CX - R - 10} y={CY + 4} textAnchor="end" className="fill-ink-muted" fontSize={11}>
          {EIXOS_RADAR[3].label}
        </text>

        {/* um polígono por empresa; preenchimento translúcido para as áreas
            sobrepostas continuarem legíveis */}
        {series.map((serie) => {
          const valores = EIXOS_RADAR.map((e) => serie.notas[e.key] ?? 0);
          return (
            <g key={serie.nome}>
              <polygon
                points={poligono(valores)}
                fill={serie.cor}
                fillOpacity={0.14}
                stroke={serie.cor}
                strokeWidth={2}
                strokeLinejoin="round"
              />
              {valores.map((v, i) => {
                const [x, y] = ponto(i, v);
                return (
                  // vértice com anel de 2px da cor do fundo: separa marcadores
                  // sobrepostos (a "codificação secundária" que a paleta exige)
                  <circle
                    key={i}
                    cx={x}
                    cy={y}
                    r={4}
                    fill={serie.cor}
                    stroke="#0C0C0C"
                    strokeWidth={2}
                  >
                    <title>{`${serie.nome} · ${EIXOS_RADAR[i].label}: ${v}`}</title>
                  </circle>
                );
              })}
            </g>
          );
        })}
      </svg>

      {/* legenda: identidade nunca fica só na cor do polígono */}
      <figcaption className="mt-2 flex flex-wrap justify-center gap-x-5 gap-y-1.5">
        {series.map((serie) => (
          <span key={serie.nome} className="flex items-center gap-2 text-sm">
            <span
              className="h-2.5 w-2.5 shrink-0 rounded-sm"
              style={{ backgroundColor: serie.cor }}
              aria-hidden
            />
            {serie.nome}
          </span>
        ))}
      </figcaption>
    </figure>
  );
}
