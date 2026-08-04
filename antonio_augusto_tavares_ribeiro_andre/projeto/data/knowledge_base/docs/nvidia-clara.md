# NVIDIA Clara

NVIDIA Clara é a plataforma de computação acelerada da NVIDIA para saúde e ciências da vida,
abrangendo imagem médica, genômica, descoberta de fármacos e dispositivos inteligentes. Reúne
SDKs e modelos pré-treinados específicos do domínio de saúde.

## Componentes
- **Imagem médica**: fluxos para análise de exames (radiologia, patologia), frequentemente
  apoiados pelo framework **MONAI** (open-source) para deep learning em imagem médica.
- **Genômica (Parabricks)**: pipelines de análise genômica acelerados por GPU.
- **Descoberta de fármacos (BioNeMo)**: modelos para proteínas, moléculas e screening.
- **Holoscan**: plataforma para dispositivos médicos com IA em tempo real (sensor/edge).

## Quando recomendar
Indicado para startups de **saúde e ciências da vida**: imagem médica, diagnóstico, genômica
ou descoberta de fármacos. A recomendação típica em saúde combina Clara, MONAI, NIM, NeMo
Guardrails e AI Enterprise (governança e conformidade). É tecnologia de domínio — recomendável,
não dogfooded pelo TAPI.
