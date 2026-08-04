# cuML (RAPIDS)

cuML é a biblioteca de machine learning acelerada por GPU do RAPIDS. Expõe uma API compatível
com scikit-learn para treinar e inferir modelos clássicos de ML em GPU, com grandes ganhos de
velocidade em datasets de médio e grande porte.

## Capacidades
- **Algoritmos acelerados**: KMeans, DBSCAN, regressão linear/logística, Random Forest, kNN,
  PCA, t-SNE e **UMAP** para redução de dimensionalidade.
- **Compatível com scikit-learn**: a mesma assinatura de `fit`/`predict`, facilitando a
  migração de CPU para GPU.
- **Pipeline em GPU**: opera direto sobre cuDF DataFrames, evitando cópias CPU↔GPU.
- **Escala**: integra com Dask para multi-GPU.

## Quando recomendar
Indicado para startups que treinam modelos clássicos de ML ou fazem **clustering/segmentação**
sobre muitos registros e sofrem com tempo de treino em CPU. No TAPI, cuML (KMeans + UMAP sobre
embeddings de setor/perfil) clusteriza o ecossistema de startups para o Radar de coorte; o
fallback de de-risking é scikit-learn em CPU.
