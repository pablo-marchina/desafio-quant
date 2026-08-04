# Guia de estilo — DataStream

Este arquivo é a referência visual para todas as telas da plataforma. Os valores
canônicos estão em `app/globals.css` e `tailwind.config.ts`; novas telas devem usar
os tokens, nunca cores hexadecimais avulsas.

## Direção visual

- Interface escura, densa e orientada a dados.
- Verde NVIDIA é reservado para ação principal, seleção, sucesso e progresso.
- Vermelho indica erro ou descarte; amarelo indica revisão ou atenção.
- Bordas discretas separam superfícies. Sombras são usadas apenas em overlays.
- A informação deve continuar compreensível sem depender exclusivamente da cor.

## Cores

| Token Tailwind | Uso |
|---|---|
| `background` | fundo geral (`#060a0f` aproximado) |
| `card` | cards, tabelas e painéis |
| `foreground` | texto principal |
| `muted-foreground` | rótulos, metadados e texto secundário |
| `border` | divisores e contornos |
| `primary` | ação, sucesso e destaque (`#76B900`) |
| `warning` | revisão e atenção |
| `destructive` | falha, rejeição e descarte |

Opacidades recomendadas: fundos de destaque em 10–15%, bordas em 20–30% e
hover branco em 2,5–5%.

## Tipografia

- Família: Inter, carregada via `next/font`.
- Título de página: 24 px, semibold.
- Título de seção/card: 14–16 px, semibold.
- Corpo: 14 px.
- Tabelas e metadados: 12 px.
- Eyebrow/rótulo técnico: 10 px, caixa alta e tracking aumentado.
- Números de KPI: 24 px, semibold, com `tracking-tight`.

## Espaçamento e geometria

- Unidade-base: 4 px.
- Espaço entre blocos do dashboard: 12 px.
- Padding de cards: 16 px.
- Raio padrão: 10 px; badges e controles menores: 6 px.
- Sidebar desktop: 230 px; topbar: 74 px; conteúdo máximo: 1500 px.
- Toda tela deve funcionar a partir de 320 px. Tabelas densas podem usar rolagem
  horizontal, mas filtros e ações devem reorganizar em coluna.

## Componentes

- Reutilize os componentes de `components/ui`, compatíveis com a convenção do
  shadcn/ui.
- Botão principal: verde sólido. Ações secundárias: `outline`. Ações de barra:
  `ghost`.
- Cards: uma borda, fundo `card`, sem sombra permanente.
- Status: badge com ícone ou texto explícito. Nunca use apenas um ponto colorido.
- Estados obrigatórios em componentes de dados: carregando, erro com retry, vazio
  e “dados insuficientes”.
- Tabelas: cabeçalho secundário, linha inteira clicável e paginação controlada
  pela API.

## Ícones e gráficos

- Use somente `lucide-react`, normalmente em 16–18 px e traço padrão.
- Não misture emojis, glyphs ou outras famílias de ícones.
- Gráficos usam Recharts. Grade em branco com baixa opacidade, série principal
  verde e tooltip com superfície `card`.
- Não derive séries ou percentuais sem base no contrato da API.

## Acessibilidade

- Alvo mínimo de interação: 36 px; prefira 40 px em ações primárias.
- Todo botão apenas com ícone deve ter `aria-label`.
- Mantenha foco visível em verde e contraste WCAG AA.
- Erros devem explicar a ação corretiva; ausência de dados deve ser diferenciada
  de falha de rede.
