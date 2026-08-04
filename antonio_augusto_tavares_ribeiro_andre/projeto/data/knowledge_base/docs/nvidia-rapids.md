# NVIDIA RAPIDS

RAPIDS é um conjunto de bibliotecas open-source da NVIDIA para executar pipelines de ciência
de dados e analytics inteiramente em GPU, mantendo APIs familiares do ecossistema Python
(pandas, scikit-learn, Spark). Acelera de ETL a machine learning em ordens de magnitude.

## Componentes
- **cuDF**: DataFrames em GPU, drop-in para pandas (ETL, joins, group-by, limpeza/dedup).
- **cuML**: machine learning em GPU, compatível com scikit-learn (clustering, regressão, kNN).
- **cuGraph**: análise de grafos acelerada.
- **Integrações**: Dask e Spark para escalar em múltiplas GPUs/nós; Accelerator zero-code-change.

## Quando recomendar
Indicado para startups que processam **grandes volumes de dados tabulares** e enfrentam
janelas de ETL/treino longas em CPU. Migrar o pipeline para RAPIDS reduz drasticamente o
tempo de feature engineering e treino, liberando ciclos de produto. No próprio TAPI, RAPIDS
(cuDF + cuML) normaliza/deduplica a coorte de startups e clusteriza o ecossistema para o
Radar de portfólio.
