# Prompt — Gerar JSON de Conhecimento NVIDIA

> Envie este prompt para qualquer LLM (Gemini, Claude, ChatGPT) seguido do conteúdo bruto que você quer transformar em JSON.

---

```
Você é um especialista em tecnologias NVIDIA e em sistemas de RAG (Retrieval-Augmented Generation).

Sua tarefa é transformar o conteúdo que será fornecido abaixo em um JSON estruturado para ser indexado em um banco vetorial. Esse banco é consultado por um agente que recomenda tecnologias NVIDIA para startups brasileiras.

---

## SCHEMA OBRIGATÓRIO

O JSON deve ter exatamente estes campos:

{
  "url": string,        // URL canônica da fonte original. Se não houver, use a URL oficial da tecnologia em nvidia.com
  "fonte": string,      // Domínio da URL, ex: "nvidia.com" ou "developer.nvidia.com"
  "titulo": string,     // Título claro e descritivo, ex: "NVIDIA NIM — Microservices de Inferência para LLMs"
  "categoria": string,  // Um dos valores abaixo
  "familia": string,    // Um dos valores abaixo
  "tecnologia": string, // Nome exato da tecnologia NVIDIA, ex: "NIM", "TensorRT", "NeMo"
  "setores": [string],  // Lista com um ou mais valores abaixo
  "ia_tipos": [string], // Lista com um ou mais valores abaixo
  "texto": string       // Texto descritivo rico (veja instruções)
}

---

## VALORES CONTROLADOS

categoria (escolha exatamente um):
- "produto"      → tecnologia ou ferramenta NVIDIA (SDK, framework, plataforma)
- "conceito"     → explicação de conceito técnico (inferência, quantização, etc.)
- "caso_de_uso"  → aplicação real em um setor ou empresa
- "inception"    → conteúdo sobre o programa NVIDIA Inception para startups
- "stack"        → combinação de tecnologias NVIDIA para resolver um problema

familia (escolha exatamente uma):
- "inferencia"   → TensorRT, TensorRT-LLM, Triton, NIM, Dynamo
- "treinamento"  → NeMo, CUDA, cuDNN
- "dados"        → RAPIDS, cuDF, cuML, cuOpt
- "deployment"   → NIM, GPU Operator, Run:ai
- "plataforma"   → DGX, NGC, AI Enterprise, Nemotron, Metropolis, Isaac, Jetson

setores (escolha todos que se aplicam, ou ["geral"] se for universal):
"saude" | "financas" | "agro" | "varejo" | "industria" | "educacao" | "energia" | "logistica" | "geral"

ia_tipos (escolha todos que se aplicam):
"visão computacional" | "NLP" | "LLM" | "recomendacao" | "series temporais" | "deteccao de anomalias" | "classificacao" | "geracao de conteudo" | "busca semantica"

---

## INSTRUÇÕES PARA O CAMPO "texto"

Este é o campo mais importante. Siga estas regras:

1. Escreva em português do Brasil, em linguagem técnica mas acessível
2. Inclua obrigatoriamente:
   - O que é a tecnologia e qual problema ela resolve
   - Casos de uso concretos (com exemplos de setores ou tipos de empresa)
   - Vantagens técnicas mensuráveis (latência, throughput, custo, escala)
   - Quais outros produtos NVIDIA se integram com esta tecnologia
   - Quando uma startup deveria escolher esta tecnologia
3. Tamanho ideal: 4 a 8 parágrafos (o texto será dividido automaticamente em chunks)
4. Não use listas com marcadores — escreva em prosa corrida
5. Não inclua informações de preço ou disponibilidade temporal

---

## EXEMPLO DE SAÍDA ESPERADA

{
  "url": "https://www.nvidia.com/en-us/ai-data-science/products/nemo/",
  "fonte": "nvidia.com",
  "titulo": "NVIDIA NeMo — Framework para Treinamento e Fine-tuning de LLMs",
  "categoria": "produto",
  "familia": "treinamento",
  "tecnologia": "NeMo",
  "setores": ["geral"],
  "ia_tipos": ["LLM", "NLP", "geracao de conteudo"],
  "texto": "NVIDIA NeMo é um framework de código aberto projetado para construir, customizar e fazer deploy de modelos de linguagem grandes (LLMs) e outros modelos de IA generativa em escala de produção. Ele oferece uma pipeline end-to-end que cobre desde o pré-treinamento com dados brutos até o fine-tuning supervisionado, alinhamento com RLHF e quantização para inferência eficiente.\n\nStartups que precisam adaptar modelos fundacionais para domínios específicos — como atendimento ao cliente em português, análise de documentos jurídicos ou geração de conteúdo médico — encontram no NeMo uma base sólida. O framework suporta técnicas modernas como LoRA, P-Tuning e SFT, que permitem customizar modelos com conjuntos de dados menores sem retreinar do zero, reduzindo significativamente o custo computacional.\n\nO NeMo integra nativamente com o NVIDIA Megatron para paralelismo de modelos em clusters multi-GPU, com o NVIDIA TensorRT-LLM para otimização de inferência após o treinamento, e com o NVIDIA NIM para empacotamento e deploy do modelo como microservice. Essa integração permite que uma startup treine no NeMo e coloque o modelo em produção com latência de inferência otimizada sem mudar de ecossistema.\n\nCasos de uso típicos incluem: empresas de saúde que treinam modelos sobre prontuários médicos em português; startups de finanças que constroem assistentes especializados em regulação e compliance; plataformas de educação que geram conteúdo personalizado em escala. O NeMo também é a base técnica dos modelos Nemotron da NVIDIA, que podem ser usados como ponto de partida para fine-tuning."
}

---

## REGRAS FINAIS

- Retorne APENAS o JSON válido, sem texto antes ou depois
- Se o conteúdo recebido cobrir mais de uma tecnologia distinta, retorne uma lista JSON: [{...}, {...}]
- Se um campo não puder ser determinado com certeza a partir do conteúdo, use o valor mais provável e conservador
- Nunca invente especificações técnicas (números, benchmarks) que não estejam no conteúdo recebido
- O campo "tecnologia" deve ser o nome canônico NVIDIA (ex: "TensorRT-LLM", não "TRT-LLM" ou "tensorrt llm")

---

## CONTEÚDO PARA TRANSFORMAR EM JSON:

[COLE O CONTEÚDO AQUI]
```
