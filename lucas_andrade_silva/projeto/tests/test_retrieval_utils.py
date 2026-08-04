import unittest

from rag.retrieval.utils import (
    filter_diversity,
    fuse_ranked_groups,
    matches_scope,
    select_adaptive_results,
    tokenize,
    weighted_rrf,
)


class RetrievalUtilsTests(unittest.TestCase):
    def test_tokenize_normalizes_case_and_punctuation(self):
        self.assertEqual(tokenize("NIM, API-compatible!"), ["nim", "api-compatible"])

    def test_rrf_rewards_items_present_in_both_rankings(self):
        vector_hits = {
            "a": {"chunk_id": "a"},
            "b": {"chunk_id": "b"},
        }
        bm25_hits = {
            "b": {"chunk_id": "b", "bm25_score": 2.0},
            "c": {"chunk_id": "c", "bm25_score": 1.0},
        }

        results = weighted_rrf(vector_hits, bm25_hits, 0.6, 0.4, 60)

        self.assertEqual(results[0]["chunk_id"], "b")

    def test_diversity_preserves_order_and_limits_sources(self):
        results = [
            {"chunk_id": "a1", "source_url": "a"},
            {"chunk_id": "a2", "source_url": "a"},
            {"chunk_id": "a3", "source_url": "a"},
            {"chunk_id": "b1", "source_url": "b"},
        ]

        filtered = filter_diversity(results, max_per_source=2)

        self.assertEqual([item["chunk_id"] for item in filtered], ["a1", "a2", "b1"])

    def test_multi_query_rrf_rewards_results_found_by_multiple_queries(self):
        groups = [
            [{"chunk_id": "a"}, {"chunk_id": "b"}],
            [{"chunk_id": "b"}, {"chunk_id": "c"}],
        ]

        results = fuse_ranked_groups(groups, [1.0, 0.8], 60)

        self.assertEqual(results[0]["chunk_id"], "b")

    def test_scope_matches_service_and_category(self):
        chunk = {"services": ["NIM Microservices"], "categories": ["Software de IA"]}

        self.assertTrue(matches_scope(chunk, "NIM Microservices", "Software de IA"))
        self.assertFalse(matches_scope(chunk, "DGX Cloud", None))

    def test_adaptive_selection_covers_each_target_service(self):
        results = [
            {"chunk_id": "d1", "source_url": "d", "services": ["DGX Cloud"]},
            {"chunk_id": "d2", "source_url": "d", "services": ["DGX Cloud"]},
            {"chunk_id": "d3", "source_url": "d-alt", "services": ["DGX Cloud"]},
            {"chunk_id": "o1", "source_url": "o", "services": ["Omniverse Cloud"]},
            {"chunk_id": "o2", "source_url": "o", "services": ["Omniverse Cloud"]},
            {"chunk_id": "o3", "source_url": "o-alt", "services": ["Omniverse Cloud"]},
            {"chunk_id": "n1", "source_url": "n", "services": ["NIM Microservices"]},
            {"chunk_id": "n2", "source_url": "n", "services": ["NIM Microservices"]},
            {"chunk_id": "n3", "source_url": "n-alt", "services": ["NIM Microservices"]},
        ]

        selected = select_adaptive_results(
            results,
            ["DGX Cloud", "Omniverse Cloud", "NIM Microservices"],
        )

        self.assertEqual(len(selected), 6)
        for service in ("DGX Cloud", "Omniverse Cloud", "NIM Microservices"):
            self.assertEqual(
                sum(service in result["services"] for result in selected),
                2,
            )
        self.assertEqual(len({result["source_url"] for result in selected}), 6)


if __name__ == "__main__":
    unittest.main()
