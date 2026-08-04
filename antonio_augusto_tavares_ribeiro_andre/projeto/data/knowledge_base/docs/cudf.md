# cuDF (RAPIDS)

cuDF é a biblioteca de DataFrames acelerada por GPU do RAPIDS. Oferece uma API quase
idêntica à do pandas para carregar, transformar, agregar e limpar dados tabulares, executando
as operações em GPU para ganhos de throughput de ordens de magnitude em datasets grandes.

## Capacidades
- **Drop-in para pandas**: `cudf.pandas` permite acelerar código pandas existente com pouca
  ou nenhuma mudança (zero-code-change accelerator).
- **ETL em GPU**: leitura de CSV/Parquet/ORC, joins, group-by, filtros e janelas em GPU.
- **Limpeza e deduplicação**: normalização e dedup de grandes volumes muito mais rápidas que
  em CPU — útil para consolidar bases sujas de múltiplas fontes.
- **Interoperabilidade**: integra com cuML, Dask-cuDF (multi-GPU) e o ecossistema Arrow.

## Quando recomendar
Indicado quando a startup tem **ETL/feature engineering pesado** sobre dados tabulares e o
pipeline em pandas/CPU virou gargalo. No TAPI, cuDF faz a normalização e a dedup da tabela
`company` acumulada antes do clustering setorial (camada de coorte).
