# MONAI

MONAI (**Medical Open Network for AI**) é o framework open-source baseado em PyTorch para deep
learning em **imagem médica**, co-liderado pela NVIDIA e pelo King's College London dentro de um
consórcio acadêmico e industrial. Oferece blocos específicos do domínio de saúde (transforms,
arquiteturas de rede, funções de perda e métricas para imagens 2D/3D), acelerados por GPU.

## Componentes
- **MONAI Core**: transforms, redes e métricas voltadas a radiologia, patologia e outras
  modalidades; leitura de formatos clínicos (DICOM/NIfTI) e pipelines de treino reproduzíveis.
- **MONAI Label**: anotação assistida por IA com active learning, reduzindo o custo de rotular
  exames médicos.
- **MONAI Deploy**: empacota e implanta apps de IA médica em fluxos clínicos (MONAI Application
  Package — MAP).
- **Model Zoo (bundles)**: modelos pré-treinados prontos para transfer learning em saúde.
- **Federated learning**: treino federado (via NVIDIA FLARE) preservando dados sensíveis de
  pacientes.

## Quando recomendar
Indicado para startups de **saúde e ciências da vida** focadas em **imagem médica** — radiologia,
patologia, diagnóstico por imagem — que precisam treinar, rotular e implantar modelos clínicos.
Combina bem com **NVIDIA Clara** (plataforma de saúde), **NIM** (servir os modelos), **NeMo
Guardrails** e **AI Enterprise** (governança e conformidade). É tecnologia de domínio — o TAPI a
recomenda quando o perfil é saúde, mas não a dogfooda.
