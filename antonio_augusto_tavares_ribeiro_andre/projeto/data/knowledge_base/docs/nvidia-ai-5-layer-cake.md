# NVIDIA — "AI Is a 5-Layer Cake" (§10.1, grounding)

Snapshot curado do post do NVIDIA Blog (framing de Jensen Huang), citável pela URL canônica. É um
dos materiais conceituais do §10.1: enquadra **onde está a stack de IA e onde o valor é capturado**,
fundamentando o pilar de otimização técnica do AIMI (F0.11). Autoria NVIDIA, mas entra como
**grounding** (definição conceitual), não como página de produto.

## As 5 camadas (base → topo)
1. **Energia** — geração de energia em tempo real; a restrição fundamental de quanta inteligência o
   sistema produz.
2. **Chips** — processadores que convertem energia em computação com eficiência, paralelismo e banda.
3. **Infraestrutura** — data centers / "AI factories": energia, refrigeração, rede e orquestração de
   dezenas de milhares de processadores.
4. **Modelos** — sistemas que entendem linguagem, biologia, física etc. (LLM é só uma categoria).
5. **Aplicações** — onde o **valor econômico** se materializa (descoberta de fármacos, robótica,
   veículos autônomos, copilotos…).

## Argumento central
"Cada aplicação bem-sucedida **puxa todas as camadas abaixo dela, até a usina** que a mantém viva."
As camadas precisam **escalar juntas**: o valor está no topo (aplicação), mas depende de descer e
**possuir/otimizar** as camadas de modelos e infraestrutura — não de consumir só a ponta como
commodity.

## Grounding da rubrica AIMI
Mapeia sobretudo no **P3 — Technical Optimization** (★ gatilho primário; ver `docs/ARQUITETURA.md §3.6`):
uma startup AI-native que vive só na camada de aplicação sobre **API crua** é frágil; "graduar"
descendo para modelos/infra próprios (**NIM, TensorRT-LLM, Triton, RAPIDS**) é exatamente "puxar as
camadas abaixo". Combina com a "corrida contra o modelo" da Sequoia: é a base conceitual do **GPU
Graduation Engine (F6.3)** e do ROI quantificado (F6.11).
