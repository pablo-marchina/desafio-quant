"""Triton Python backend for cross-encoder reranking.

Model: cross-encoder/ms-marco-MiniLM-L-6-v2
Returns sigmoid-normalized relevance scores for (query, document) pairs.
"""

import math
import os

import numpy as np
import triton_python_backend_utils as pb_utils


class TritonPythonModel:
    def initialize(self, args):
        model_name = os.environ.get("CE_MODEL_NAME", "cross-encoder/ms-marco-MiniLM-L-6-v2")
        from sentence_transformers import CrossEncoder

        # config.pbtxt declares KIND_CPU. Keep the Python model on CPU as well so
        # local execution is deterministic and does not require a host GPU.
        self.model = CrossEncoder(model_name, device="cpu")

    def execute(self, requests):
        responses = []
        for request in requests:
            query = pb_utils.get_input_tensor_by_name(request, "query").as_numpy()[0].decode("utf-8")
            documents = pb_utils.get_input_tensor_by_name(request, "documents").as_numpy()

            pairs = [[query, doc[0].decode("utf-8")] for doc in documents]
            logits = self.model.predict(pairs, batch_size=len(pairs), show_progress_bar=False)
            scores = [1.0 / (1.0 + math.exp(-max(min(float(logit), 20.0), -20.0))) for logit in logits]

            out_tensor = pb_utils.Tensor("scores", np.array(scores, dtype=np.float32))
            responses.append(pb_utils.InferenceResponse([out_tensor]))
        return responses

    def finalize(self):
        pass
