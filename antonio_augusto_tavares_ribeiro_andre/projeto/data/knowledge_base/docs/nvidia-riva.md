# NVIDIA Riva

NVIDIA Riva é o conjunto de microsserviços e modelos para IA de fala (speech AI) em produção,
multilíngue e com baixa latência, disponível para deploy via NIM em nuvem, data center ou
edge. Cobre toda a cadeia de voz, não só transcrição.

## Capacidades
- **ASR (reconhecimento de fala)**: transcrição em tempo real e em lote, com alta acurácia e
  suporte a customização de vocabulário/domínio. É o componente que o próprio TAPI usa para
  transcrever os vídeos do §10.1 para a base de conhecimento.
- **TTS (síntese de fala)**: vozes naturais e customizáveis para respostas faladas.
- **Tradução de fala (S2S/NMT)** e modelos de voz para pipelines de conversação.
- **Deploy otimizado**: servido com Triton/TensorRT para latência baixa em GPU.

## Quando recomendar
Indicado para startups de **voz, call center ou transcrição**: a recomendação típica é
Riva (ASR/TTS) + NIM para servir a inferência com baixa latência e custo controlado. Endereça
casos de produto centrados em fala — gap de **Workflow Depth** quando há automação de
atendimento por voz. O TAPI dogfooda apenas o ASR; TTS e voz entram como recomendáveis.
