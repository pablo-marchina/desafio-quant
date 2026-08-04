cuDF

Url: https://docs.rapids.ai/api/cudf/stable/

Resumo: processamento de dataframes em GPU

cuDF (pronounced “KOO-dee-eff”) is a Python GPU DataFrame library (built on the Apache Arrow columnar memory format) for loading, joining, aggregating, filtering, and otherwise manipulating data. cuDF also provides a pandas-like API that will be familiar to data engineers & data scientists, so they can use it to easily accelerate their workflows without going into the details of CUDA programming.

cudf.pandas is built on cuDF and accelerates pandas code on the GPU. It supports 100% of the pandas API, using the GPU for supported operations, and automatically falling back to pandas for other operations.